"""Las piezas del bloqueo por directorio que comparten sus dos tomadores.

`vault_fs.file_lock` (scripts) y `_FileLock` de `vault.autoria.conocimiento`
(paquete, que no importa `scripts/`) toman el **mismo** lock sobre la misma
nota. Hasta v40.36 cada uno escribía estas piezas por su cuenta y divergieron
dos veces: dd593d0 (cada uno nombraba el directorio a su manera y los dos
escribían a la vez) y ad5b10b (el hueco del borrado pendiente hubo que
arreglarlo en los dos sitios). Lo que tiene que ser igual en ambos vive aquí;
desde v41.3 también el bucle de adquisición, con la caducidad y `owner.json`
(`adquirir`/`soltar`). La reentrancia por hilo sigue en `vault_fs`. Tras v41.6,
el huérfano lo decide el dueño (`_huerfano`) y la escritura comprueba que la
toma sigue siendo suya antes de reemplazar (`comprobar_toma`).

Hoja del núcleo: solo stdlib.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

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
    """`(.locks/, .locks/<nombre>.lock)` de `objetivo`: un solo nombre por nota.

    La ruta se normaliza con `os.path.realpath` antes de derivar nada
    (auditoría del 2026-10-15). La toma de cada hilo se guarda por
    `str(lock_dir)`, y sin normalizar, quien tomaba el lock con una forma de la
    ruta —relativa, con `..`, con el nombre 8.3 de TEMP en Windows— y escribía
    con otra no encontraba su toma: `comprobar_toma` volvía sin comprobar nada.
    `realpath` y no `Path.resolve`: en 3.9 sobre Windows `resolve()` de una ruta
    relativa que no existe puede devolverla relativa (bpo-38671). Límite: el
    último componente de una nota que aún no existe conserva la caja con que
    llega, así que en un disco que no distingue mayúsculas `Nota.md` y
    `nota.md` siguen siendo dos locks hasta que la nota existe.
    """
    objetivo = Path(os.path.realpath(objetivo))
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


#: Edad a partir de la cual un lock se da por huérfano cuando no se puede
#: preguntar por su dueño: otra máquina, o un `owner.json` anterior a v41.6.
CADUCA_TRAS = 120.0


def maquina() -> str:
    """Quién puede preguntar por el pid de `owner.json`: host y plataforma.

    La plataforma va porque WSL y Windows comparten el nombre de host pero no
    el espacio de pids: desde Linux, un pid de Windows no existe, y se daría
    por muerto al dueño vivo de una carpeta montada en `/mnt/c`.
    """
    return f"{socket.gethostname()}|{sys.platform}"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    _kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _CONSULTA_LIMITADA = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
    _SIGUE_ACTIVO = 259  # STILL_ACTIVE
    _PARAMETRO_INVALIDO = 87  # ERROR_INVALID_PARAMETER: no hay proceso con ese pid

    def _consultar(pid: int) -> Tuple[Optional[bool], Optional[str]]:
        # `os.kill(pid, 0)` no sirve aquí: en Windows termina el proceso.
        h = _kernel32.OpenProcess(_CONSULTA_LIMITADA, False, pid)
        if not h:
            if ctypes.get_last_error() == _PARAMETRO_INVALIDO:
                return False, None
            return None, None  # existe pero no se deja consultar
        try:
            codigo = wintypes.DWORD()
            if not _kernel32.GetExitCodeProcess(h, ctypes.byref(codigo)):
                return None, None
            if codigo.value != _SIGUE_ACTIVO:
                return False, None
            tiempos = [wintypes.FILETIME() for _ in range(4)]
            if not _kernel32.GetProcessTimes(h, *(ctypes.byref(t) for t in tiempos)):
                return True, None
            creado = tiempos[0]
            return True, str((creado.dwHighDateTime << 32) | creado.dwLowDateTime)
        finally:
            _kernel32.CloseHandle(h)

else:

    def _consultar(pid: int) -> Tuple[Optional[bool], Optional[str]]:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False, None
        except PermissionError:
            pass  # vive, de otro usuario
        except OSError:
            return None, None
        # En Linux la hora de inicio es el campo 22 de /proc/<pid>/stat, en
        # ticks desde el arranque; el nombre del ejecutable va entre paréntesis
        # y puede llevar espacios, así que se cuenta desde el último `)`.
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
            return True, stat[stat.rfind(")") + 2:].split()[19]
        except (OSError, IndexError):
            return True, None


def proceso_vivo(pid: int) -> Optional[bool]:
    """True/False si este proceso puede saberlo; None si no puede."""
    return _consultar(pid)[0]


def inicio_del_proceso(pid: int) -> Optional[str]:
    """Hora de inicio de `pid` como marca opaca, o None si no se publica.

    Distingue al dueño de un proceso que heredó su pid: el pid solo no basta,
    porque el sistema lo reutiliza.
    """
    return _consultar(pid)[1]


def _dueno_vive(dueno: dict) -> Optional[bool]:
    """Si el dueño de `owner.json` sigue dentro, cuando se puede saber.

    Solo se pregunta en la misma máquina; fuera de ella, o con un `owner.json`
    sin `maquina` (escrito hasta v41.6 incluida), devuelve None y decide la edad.
    """
    if dueno.get("maquina") != maquina():
        return None
    try:
        pid = int(dueno["pid"])
    except (KeyError, TypeError, ValueError):
        return None
    vive, inicio = _consultar(pid)
    if vive and dueno.get("inicio") and inicio and dueno["inicio"] != inicio:
        return False  # el pid es ya de otro proceso
    return vive


def _huerfano(lock_dir: Path, caduca_tras: float) -> bool:
    """Si `lock_dir` se puede robar: dueño muerto, o sin dueño consultable y viejo.

    Hasta v41.6 incluida decidía solo la edad, medida con el reloj de pared: un salto de
    3458 s en python:3.9-slim sobre Docker Desktop le robó el lock a un dueño
    vivo de 1,2 s y `vault_append` escribió sobre una nota bloqueada (deuda
    `lock_caduca_por_reloj_de_pared`). Ahora, en la misma máquina y con un dueño
    consultable, el reloj no interviene: un dueño vivo conserva el lock aunque
    lleve horas —quien espera sale por su timeout, como con `index.lock` de
    git— y uno muerto se recupera sin esperar `CADUCA_TRAS`. Sin `owner.json`
    legible, desde otra máquina o sin poder consultar el proceso, sigue
    decidiendo la edad, y con ella el reloj.
    """
    try:
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dueno = None
    if isinstance(dueno, dict):
        vive = _dueno_vive(dueno)
        if vive is not None:
            return not vive
    return _edad(lock_dir) > caduca_tras


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


_INICIOS: Dict[int, Optional[str]] = {}


def _inicio_propio() -> Optional[str]:
    # Por pid y no una vez por módulo: un hijo de `fork` hereda el módulo.
    pid = os.getpid()
    if pid not in _INICIOS:
        _INICIOS[pid] = inicio_del_proceso(pid)
    return _INICIOS[pid]


def ficha_del_dueno(token: str) -> Dict[str, object]:
    """El `owner.json` que escribe una toma de este proceso con `token`.

    Público para que quien simula un lock tomado —los tests de «nota tomada»—
    escriba el mismo formato y no uno copiado a mano: con `{"pid": 0, …}` sin
    `maquina` caían en la regla de edad, y un reloj que salta ±3459 s (medido en
    python:3.9-slim sobre Docker Desktop) les robaba el lock.
    """
    return {
        "pid": os.getpid(), "createdAt": time.time(), "token": token,
        "maquina": maquina(), "inicio": _inicio_propio(),
    }


class LockPerdido(Exception):
    """La toma de este hilo ya no es la dueña del lock: no se reemplaza nada.

    Lleva `causa`, `mensaje` y `datos` para que `wrap_main` la traduzca por
    `vault_errors.emit_fallo` a NOTE_LOCKED; se lee por pato y no hereda de
    `FalloDeDominio` porque este módulo es hoja y solo usa stdlib (el mismo
    trato que `vault_fs.SecretoDetectado`).
    """

    causa = "LOCK_PERDIDO"

    def __init__(self, objetivo: Path) -> None:
        mensaje = (f"El lock de {objetivo.name} pasó a otro escritor mientras se "
                   "escribía; no se reemplazó la nota.")
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.datos = {"path": str(objetivo)}


#: Las tomas vivas de cada hilo, `str(lock_dir) -> token`. Por hilo y no por
#: proceso: la reentrancia de `vault_fs.file_lock` también es por hilo, y una
#: escritura de otro hilo no escribe bajo esta toma.
_TOMAS = threading.local()


def _tomas() -> Dict[str, str]:
    if not hasattr(_TOMAS, "vivas"):
        _TOMAS.vivas = {}
    return _TOMAS.vivas


def comprobar_toma(objetivo: Path) -> None:
    """Lanza `LockPerdido` si este hilo tomó el lock de `objetivo` y ya no es suyo.

    El fencing de Kleppmann reducido a lo que admite un sistema de ficheros:
    quien escribe relee `owner.json` justo antes de reemplazar. Sin toma
    registrada no hay nada que comprobar —la escritura no va bajo este lock—.
    Comprobación y replace no son atómicos entre sí: la ventana se estrecha a
    microsegundos, no se cierra.
    """
    _, lock_dir = rutas_de_lock(objetivo)
    token = _tomas().get(str(lock_dir))
    if token is None:
        return
    try:
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dueno = None  # retirado: el ladrón ya entró y soltó
    if not (isinstance(dueno, dict) and dueno.get("token") == token):
        raise LockPerdido(objetivo)


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
                if _huerfano(lock_dir, caduca_tras):
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
                json.dumps(ficha_del_dueno(token)),
                encoding="utf-8",
            )
            _tomas()[str(lock_dir)] = token
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
    if _tomas().get(str(lock_dir)) == token:
        del _tomas()[str(lock_dir)]
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
