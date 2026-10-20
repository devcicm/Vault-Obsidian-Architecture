"""Primitive package-owned de escritura atómica.

No decide qué nota se escribe ni conoce índices, ledger, scripts o una raíz de
runtime. Recibe una ruta ya contenida y deposita el texto mediante temporal y
``os.replace``. ``VAULT_FSYNC=1`` conserva la política histórica de
durabilidad opt-in para consumidores instalados y adaptadores legacy.
"""

from __future__ import annotations

import errno
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from .bloqueo import comprobar_toma


Guarda = Callable[[Path, str], None]

#: Errores de Windows de un destino que otro proceso tiene abierto sin
#: compartir el borrado: acceso denegado (5) y violación de compartición (32).
_COMPARTICION = {5, 32}

#: Segundos que se reintenta el `os.replace` ante esa compartición. Medido en
#: r48 (2026-10-16): un antivirus o indexador abre la nota recién reemplazada
#: y el siguiente escritor, ya con el lock, recibía PERMISSION_DENIED.
PLAZO_DE_COMPARTICION = 2.0


def _fsync_enabled() -> bool:
    # Conserva la semántica de ``vault_entorno.leer``: sólo ``"1"`` activa
    # la durabilidad opt-in. Aceptar otros valores cambiaría silenciosamente
    # el contrato de los scripts legacy.
    return os.environ.get("VAULT_FSYNC") == "1"


def _escribir_temporal(temp: Path, text: str, encoding: str) -> None:
    """Escribe el temporal y sincroniza su descriptor si se solicitó."""
    # `newline=""`: el texto se deposita tal cual. Sin él, Windows traducía
    # cada `\n` a `\r\n` y deshacía el LF que el saneado acababa de fijar.
    with open(temp, "w", encoding=encoding, newline="") as handle:
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


def _reemplazar(temporary: Path, path: Path) -> None:
    """`os.replace` con reintento acotado de la compartición transitoria de Windows.

    El mismo transitorio que `bloqueo.soltar` ya reintenta con los locks. En
    POSIX un `PermissionError` no lleva `winerror` y sale a la primera: allí sí
    es un permiso. El fencing va antes de cada intento —quien pierde el lock
    mientras espera no reemplaza— y agotado el plazo se propaga el error.
    """
    hasta = time.monotonic() + PLAZO_DE_COMPARTICION
    while True:
        # Lo último antes del replace: quien perdió el lock de `path` mientras
        # escribía el temporal no pisa lo que escribió quien se lo quitó.
        comprobar_toma(path)
        try:
            os.replace(temporary, path)
            return
        except PermissionError as exc:
            if (getattr(exc, "winerror", None) not in _COMPARTICION
                    or time.monotonic() >= hasta):
                raise
        time.sleep(0.02)


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
        _reemplazar(temporary, path)
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


def apartar_ilegible(path: Path) -> Path:
    """Renombra `path` a `<nombre>.ilegible-<utc>-<hex>` y devuelve la ruta nueva.

    Para los registros de efecto lateral —trazas, contadores, logs de
    arreglos— que no deben tumbar la operación que anotan: un JSON que no se lee
    se **aparta** en vez de leerse como vacío y pisarse con la entrada nueva
    (auditoría del 2026-10-15, AP-51). El contenido queda entero junto al
    original para repararlo a mano, y el nombre queda libre para seguir.
    `os.replace` en el mismo directorio: no hay copia a medias.
    """
    sello = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    destino = path.with_name(f"{path.name}.ilegible-{sello}-{uuid.uuid4().hex[:6]}")
    os.replace(path, destino)
    return destino


# ── Mismo cuerpo ⇒ mismo documento (v41.12, el C3 del auditor) ──────────────


def _sin_sellos(datos: Any, sellos: frozenset) -> Any:
    """El cuerpo de un JSON sin sus claves de sello: lo que identifica el doc.

    Recurre en dicts y listas: los sellos pueden vivir anidados (los de
    `vault_graph_merge` cuelgan de `diagnostics.silo_flags`). Los JSON del
    dominio no tienen ciclos, así que la recursión es segura.
    """
    if isinstance(datos, dict):
        return {k: _sin_sellos(v, sellos) for k, v in datos.items()
                if k not in sellos}
    if isinstance(datos, list):
        return [_sin_sellos(v, sellos) for v in datos]
    return datos


def escribir_json_si_cambia(
    escribir_json: Callable[[Path, dict], None],
    ruta: Path,
    datos: dict,
    claves_de_sello: frozenset = frozenset(),
) -> bool:
    """Escribe `datos` solo si el cuerpo (sin sellos) difiere del disco.

    Devuelve True si escribió. Sin esto, cada regeneración de un índice o
    registro movía su sello de tiempo (`rebuiltAt`, `updated_at`, …) y el
    diff de bytes daba por trabajo una regeneración que no cambió nada — el
    parpadeo que el C3 del auditor midió por hash de contenido en la ola O1.

    Vive en el kernel porque lo llaman tres contextos distintos (Índices,
    Grafo, Gobernanza) y un cruce hacia Índices solo para traer esta función
    era deuda de arquitectura sin motivo. ES del kernel lo genérico: el
    mecanismo de comparar contra disco y decidir. Lo del dominio —qué claves
    son sello en SUS ficheros— lo declara cada llamador en `claves_de_sello`;
    el kernel no conoce ni `rebuiltAt` ni `updated_at`.

    `escribir_json` es la función del canal (bound method del puerto o
    `atomic_write_json`): el que compara pide la escritura, no la implementa.
    """
    sellos = frozenset(claves_de_sello or frozenset())
    cuerpo = _sin_sellos(datos, sellos)
    try:
        previo = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previo = None
    if isinstance(previo, dict) and _sin_sellos(previo, sellos) == cuerpo:
        return False
    escribir_json(ruta, datos)
    return True
