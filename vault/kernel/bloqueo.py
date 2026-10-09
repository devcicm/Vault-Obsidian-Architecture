"""Las piezas del bloqueo por directorio que comparten sus dos tomadores.

`vault_fs.file_lock` (scripts) y `_FileLock` de `vault.autoria.conocimiento`
(paquete, que no importa `scripts/`) toman el **mismo** lock sobre la misma
nota. Hasta v40.36 cada uno escribía estas piezas por su cuenta y divergieron
dos veces: dd593d0 (cada uno nombraba el directorio a su manera y los dos
escribían a la vez) y ad5b10b (el hueco del borrado pendiente hubo que
arreglarlo en los dos sitios). Lo que tiene que ser igual en ambos vive aquí;
desde v41.3 también el bucle de adquisición, con la caducidad y `owner.json`
(`adquirir`/`soltar`). La reentrancia por hilo sigue en `vault_fs`.

Hoja del núcleo: solo stdlib.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Tuple

#: Cuánto se reintenta el hueco de un `.locks/` en borrado pendiente. Soltar el
#: último lock de una carpeta lo retira, y en Windows un directorio en borrado
#: pendiente sigue ocupando el nombre un instante: crearlo da FileExistsError
#: con `is_dir()` ya en falso, y crear un lock dentro da PermissionError. Medido
#: el 2026-10-05: 1 de 12 procesos moría así en
#: tests/test_file_lock_entre_procesos.py. Los mismos errores también los da
#: una carpeta en la que de verdad no se puede escribir: la ventana es corta
#: para que ese caso siga saliendo con su error y no como un timeout.
HUECO_BORRADO_PENDIENTE = 1.0


def rutas_de_lock(objetivo: Path) -> Tuple[Path, Path]:
    """`(.locks/, .locks/<nombre>.lock)` de `objetivo`: un solo nombre por nota."""
    raiz = objetivo.parent / ".locks"
    return raiz, raiz / f"{objetivo.name}.lock"


def crear_carpeta_de_locks(raiz: Path) -> None:
    """Crea `raiz` tolerando que otro proceso la esté retirando a la vez."""
    hasta = time.monotonic() + HUECO_BORRADO_PENDIENTE
    while True:
        try:
            raiz.mkdir(parents=True, exist_ok=True)
            return
        except (FileExistsError, PermissionError):
            if time.monotonic() >= hasta:
                raise
            time.sleep(0.01)


class HuecoDeBorrado:
    """La ventana del PermissionError al crear un lock dentro de un `.locks/`
    en borrado pendiente. Se abre en el primer error y no se reinicia: un
    permiso denegado de verdad sale en `HUECO_BORRADO_PENDIENTE`, no al
    agotar el timeout del lock.
    """

    def __init__(self) -> None:
        self._hasta = None

    def reintentar(self) -> bool:
        """Llamar desde `except PermissionError`: espera un instante y dice si
        se puede volver a competir, o False si la ventana se agotó."""
        ahora = time.monotonic()
        if self._hasta is None:
            self._hasta = ahora + HUECO_BORRADO_PENDIENTE
        if ahora >= self._hasta:
            return False
        time.sleep(0.01)
        return True


def retirar_carpeta_si_vacia(raiz: Path) -> bool:
    """Retira `.locks/` al soltar el último lock; True si lo retiró.

    Medido el 2026-10-05: un reindex de un vault real dejaba un `.locks/` vacío
    en cada una de sus 68 secciones. `rmdir` solo borra si está vacío; si otro
    proceso ya tiene su lock dentro falla y se queda, y quien llegue entre
    medias lo recrea (`crear_carpeta_de_locks`).
    """
    try:
        raiz.rmdir()
    except OSError:
        return False
    return True


#: Edad a partir de la cual un lock se da por huérfano: su dueño murió dentro.
CADUCA_TRAS = 120.0


def _edad(lock_dir: Path) -> float:
    """Segundos desde que se tomó `lock_dir`, por `owner.json` o por el mtime.

    `mkdir` y `owner.json` son dos pasos: tratar el hueco entre ambos como
    caducado era robar el lock a un dueño vivo de milisegundos.
    """
    try:
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        return time.time() - float(dueno.get("createdAt", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return time.time() - lock_dir.stat().st_mtime


def _vaciar(carpeta: Path) -> None:
    try:
        for hijo in carpeta.iterdir():
            hijo.unlink()
        carpeta.rmdir()
    except OSError:
        pass


def adquirir(objetivo: Path, timeout: float, caduca_tras: float = CADUCA_TRAS) -> str:
    """Toma el lock de `objetivo` entre procesos y devuelve el token de esta toma.

    El único bucle de adquisición: hasta v41.2 había uno en cada tomador, y el de
    `_FileLock` no recuperaba huérfanos ni escribía `owner.json`. Lanza
    `TimeoutError` si no llega a tiempo y deja escapar el `PermissionError` de
    una carpeta en la que de verdad no se puede escribir.
    """
    raiz, lock_dir = rutas_de_lock(objetivo)
    crear_carpeta_de_locks(raiz)
    limite = time.monotonic() + timeout
    token = uuid.uuid4().hex
    hueco = HuecoDeBorrado()
    while True:
        try:
            os.mkdir(lock_dir)
        except FileNotFoundError:
            # Otro proceso soltó el último lock y retiró `.locks/` vacío.
            crear_carpeta_de_locks(raiz)
            continue
        except PermissionError:
            # El mismo retiro visto un instante antes (borrado pendiente).
            if time.monotonic() >= limite or not hueco.reintentar():
                raise
            crear_carpeta_de_locks(raiz)
            continue
        except FileExistsError:
            try:
                if _edad(lock_dir) > caduca_tras:
                    # Robo por rename: borrarlo en su sitio deja que un segundo
                    # ladrón borre el lock que un tercero acaba de tomar.
                    # `os.replace` es atómico y solo uno lo gana.
                    robado = raiz / f"{objetivo.name}.stale.{os.getpid()}.{uuid.uuid4().hex[:8]}"
                    try:
                        os.replace(lock_dir, robado)
                    except OSError:
                        time.sleep(0.05)
                        continue
                    _vaciar(robado)
                    continue
            except OSError:
                pass
            if time.monotonic() >= limite:
                raise TimeoutError(f"Timeout waiting for lock: {lock_dir}")
            time.sleep(0.05)
            continue
        try:
            (lock_dir / "owner.json").write_text(
                json.dumps({"pid": os.getpid(), "createdAt": time.time(), "token": token}),
                encoding="utf-8",
            )
            return token
        except OSError:
            # Solo si `lock_dir` ya no está: lo dio por caducado alguien con un
            # reloj muy desviado. Se vuelve a competir desde cero.
            continue


def soltar(objetivo: Path, token: str) -> None:
    """Suelta el lock de `objetivo` solo si sigue siendo de la toma `token`.

    Un lock robado por caducado ya es de otro, y borrarlo dejaba entrar a un
    tercero con el ladrón todavía dentro (v40.34).
    """
    raiz, lock_dir = rutas_de_lock(objetivo)
    try:
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        mio = isinstance(dueno, dict) and dueno.get("token") == token
    except (OSError, ValueError):
        mio = False
    if mio:
        # Apartarlo con un rename atómico antes de vaciarlo. En Windows el rename
        # falla con PermissionError mientras otro proceso tiene `owner.json`
        # abierto para medirle la edad; es transitorio, y rendirse a la primera
        # dejaba el lock tomado hasta que caducara.
        suelto = raiz / f"{objetivo.name}.released.{token[:8]}"
        hasta = time.monotonic() + 5.0
        while True:
            try:
                os.replace(lock_dir, suelto)
                break
            except PermissionError:
                if time.monotonic() >= hasta:
                    suelto = None
                    break
                time.sleep(0.01)
            except OSError:
                suelto = None
                break
        if suelto is not None:
            _vaciar(suelto)
    retirar_carpeta_si_vacia(raiz)
