"""Primitive package-owned de escritura atómica.

No decide qué nota se escribe ni conoce índices, ledger, scripts o una raíz de
runtime. Recibe una ruta ya contenida y deposita el texto mediante temporal y
``os.replace``. ``VAULT_FSYNC=1`` conserva la política histórica de
durabilidad opt-in para consumidores instalados y adaptadores legacy.
"""

from __future__ import annotations

import errno
import os
import uuid
from pathlib import Path
from typing import Callable, Sequence


Guarda = Callable[[Path, str], None]


def _fsync_enabled() -> bool:
    # Conserva la semántica de ``vault_entorno.leer``: sólo ``"1"`` activa
    # la durabilidad opt-in. Aceptar otros valores cambiaría silenciosamente
    # el contrato de los scripts legacy.
    return os.environ.get("VAULT_FSYNC") == "1"


def _escribir_temporal(temp: Path, text: str, encoding: str) -> None:
    """Escribe el temporal y sincroniza su descriptor si se solicitó."""
    with open(temp, "w", encoding=encoding) as handle:
        handle.write(text)
        if _fsync_enabled():
            handle.flush()
            os.fsync(handle.fileno())


def _fsync_si_procede(temp: Path) -> None:
    """Sincroniza el directorio padre sólo con ``VAULT_FSYNC=1``.

    ``escritura_atomica`` ya garantiza **atomicidad** por temporal y
    ``os.replace``: ningún lector observa contenido a medio escribir. La
    **durabilidad** ante un corte es una decisión independiente. No se paga por
    defecto porque las notas son reconstruibles y algunas operaciones escriben
    cientos de archivos; quien necesita persistencia opt-in fija
    ``VAULT_FSYNC=1``. En POSIX también se sincroniza el directorio padre para
    persistir el rename; Windows no ofrece ``O_DIRECTORY`` y ese paso no aplica.
    """
    if not _fsync_enabled() or not hasattr(os, "O_DIRECTORY"):
        return
    directory_fd = os.open(str(temp.parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def escritura_atomica(
    path: Path,
    text: str,
    encoding: str = "utf-8",
    guardas: Sequence[Guarda] = (),
) -> None:
    """Escribe ``path`` por temporal→replace y limpia el temporal si falla."""
    for guarda in guardas:
        guarda(path, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    try:
        _escribir_temporal(temporary, text, encoding)
        _fsync_si_procede(temporary)
        os.replace(temporary, path)
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            exc.errno = errno.ENOSPC
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
