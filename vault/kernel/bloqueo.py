"""Las piezas del bloqueo por directorio que comparten sus dos tomadores.

`vault_fs.file_lock` (scripts) y `_FileLock` de `vault.autoria.conocimiento`
(paquete, que no importa `scripts/`) toman el **mismo** lock sobre la misma
nota. Hasta v40.36 cada uno escribía estas piezas por su cuenta y divergieron
dos veces: dd593d0 (cada uno nombraba el directorio a su manera y los dos
escribían a la vez) y ad5b10b (el hueco del borrado pendiente hubo que
arreglarlo en los dos sitios). Lo que tiene que ser igual en ambos vive aquí;
la política de cada tomador —caducidad, `owner.json`, reentrancia por hilo—
sigue en el suyo.

Hoja del núcleo: solo stdlib.
"""

from __future__ import annotations

import time
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
