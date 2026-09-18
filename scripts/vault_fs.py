#!/usr/bin/env python3
"""vault_fs — el mecanismo de escritura y exclusión mutua. Módulo hoja.

Aquí está lo que toca el sistema de ficheros y **nada de lo que decide qué se
escribe**: el lock de directorio reentrante por hilo y la escritura atómica
(temporal → `os.replace`). Ni saneado de codificación, ni ledger, ni índices de
sección, ni vocabulario de tags. Esa capa es política y se queda en `vault_io`.

**Por qué existe (v40.17).** `atomic_write_text` mezclaba las dos cosas: un
mecanismo de tres pasos envuelto en seis políticas, cada una con su import. Por
eso `vault_errors_trace` —que solo quiere depositar un JSON que él mismo
generó— arrastraba el módulo entero de IO, y con él el ciclo
`errors → errors_trace → io → encoding → errors`, esquivado a mano con imports
diferidos dentro de funciones.

La inversión: el mecanismo no conoce a la política. Cuando una escritura
necesita una comprobación previa, quien llama la **pasa** en `guardas`; este
módulo la ejecuta y no sabe qué hace. Es inyección explícita por parámetro, no
un contenedor ni un registro global: el vínculo se lee en la llamada.

**No importa ningún `vault_*` salvo `vault_entorno`** (hoja). `guarda_secretos`
importa `vault_secret_scan` de forma diferida y a propósito — es hoja también, y
así el escaneo sigue siendo opcional para quien no lo necesita sin que este
módulo dependa de él para cargar.
"""

import importlib
import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Iterator

from vault_entorno import leer as _env

# Frontera estrictamente legacy: algunos scripts se ejecutan como fichero y
# Python sólo añade ``scripts/`` al path. El producto instalado nunca importa
# este módulo. Reintentamos exclusivamente cuando falta el paquete superior;
# errores internos de ``vault.kernel.escritura`` deben seguir siendo visibles.
def _stable_escritura_module():
    """Carga el primitive estable sólo cuando una escritura legacy lo necesita."""
    try:
        return importlib.import_module("vault.kernel.escritura")
    except ModuleNotFoundError as exc:
        if exc.name != "vault":
            raise
        legacy_repo_root = Path(__file__).resolve().parent.parent
        if str(legacy_repo_root) not in sys.path:
            sys.path.insert(0, str(legacy_repo_root))
        return importlib.import_module("vault.kernel.escritura")


def __getattr__(name: str):
    """Reexporta el primitive estable sin cargarlo durante un import puro."""
    if name in {"_escribir_temporal", "_fsync_si_procede", "escritura_atomica"}:
        return getattr(_stable_escritura_module(), name)
    raise AttributeError(name)


#: Una guarda: se le da (ruta, texto) antes de escribir y aborta lanzando.
#: El mecanismo no interpreta lo que hace — solo la ejecuta y deja pasar la
#: excepción. Ver `guarda_secretos` para la única que este módulo ofrece hecha.
Guarda = Callable[[Path, str], None]


# ── Exclusión mutua ────────────────────────────────────────────────────────────
# In-process locks keyed by lock-dir path. The mkdir directory-lock below is the
# cross-PROCESS primitive, but rapid same-PROCESS mkdir/rmdir churn is racy on
# Windows (handle caching / AV), so threads in one process could both acquire.
# This threading.Lock layer serializes same-process callers deterministically;
# the mkdir layer still guards across processes.
_LOCAL_LOCKS: Dict[str, threading.Lock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


def _local_lock_for(key: str) -> threading.Lock:
    with _LOCAL_LOCKS_GUARD:
        lk = _LOCAL_LOCKS.get(key)
        if lk is None:
            lk = threading.Lock()
            _LOCAL_LOCKS[key] = lk
        return lk


#: Locks que ESTE hilo ya tiene tomados, por clave de lock-dir.
#
# Sin esto, un hilo que vuelve a pedir un lock que él mismo sostiene espera el
# timeout entero contra sí mismo y luego se le dice al llamante «no se pudo
# bloquear». Casi todos los llamantes reaccionan igual: escribir de todos modos,
# sin sincronizar. Medido en `vault_sdd_init`, que escribe con `atomic_write_text`
# y cuyo saneador de codificación traza cada corrección: 26 tomas del lock del
# fichero de trazas, 13 fallidas, 65 s de espera pura — y esas 13 acababan
# escribiendo el trace SIN lock justo mientras el llamante externo lo estaba
# reemplazando. El coste visible era que la tool se pasaba del timeout de 60 s;
# el defecto era la escritura sin sincronizar.
#
# La reentrancia se concede sin volver a tomar nada: si el hilo ya lo tiene, la
# exclusión que el lock promete YA está garantizada. Lo que no se hace es soltar
# el lock al salir del bloque interno — solo el bloque más externo libera, o el
# `finally` interno abriría la ventana que el externo cree cerrada.
_HELD_LOCKS = threading.local()


def _held(key: str) -> bool:
    return key in getattr(_HELD_LOCKS, "keys", ())


@contextmanager
def file_lock(
    target: Path, timeout: float = 30.0, stale_after: float = 120.0
) -> Iterator[Path]:
    """Create an atomic directory lock near the target file.

    This avoids lost updates when multiple documentation tools update the same
    JSON index during mass generation. Stale locks are removed after
    ``stale_after`` seconds. Layered: an in-process threading.Lock serializes
    threads in this process; the mkdir directory-lock serializes across processes.

    Reentrante por hilo: si el hilo que llama ya sostiene este mismo lock, el
    bloque se ejecuta sin volver a adquirirlo y sin liberar al salir. Ver
    `_HELD_LOCKS` para qué pasaba antes — no era una espera de más, era una
    escritura sin sincronizar.
    """
    lock_root = target.parent / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_dir = lock_root / f"{target.name}.lock"
    clave = str(lock_dir)
    deadline = time.time() + timeout

    if _held(clave):
        yield lock_dir
        return

    local = _local_lock_for(clave)
    acquired = local.acquire(blocking=False) if timeout <= 0 else local.acquire(timeout=timeout)
    if not acquired:
        raise TimeoutError(f"Timeout waiting for in-process lock: {lock_dir}")

    while True:
        try:
            os.mkdir(lock_dir)
            (lock_dir / "owner.json").write_text(
                json.dumps({"pid": os.getpid(), "createdAt": time.time()}),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            try:
                owner_file = lock_dir / "owner.json"
                if owner_file.exists():
                    try:
                        owner_data = json.loads(owner_file.read_text(encoding="utf-8"))
                        age = time.time() - owner_data.get("createdAt", 0)
                    except (json.JSONDecodeError, OSError):
                        age = stale_after + 1
                else:
                    age = stale_after + 1
                if age > stale_after:
                    # Steal-by-rename: atomically move the stale lock aside before
                    # removing it. Deleting lock_dir in place is a TOCTOU race — a
                    # second process that also saw the lock as stale could unlink the
                    # owner.json / rmdir the lock that a THIRD process just re-acquired,
                    # silently breaking mutual exclusion. os.replace is atomic and fails
                    # (OSError) if another process already stole or the owner released,
                    # so only the winner of the rename owns the cleanup.
                    steal = lock_root / f"{target.name}.stale.{os.getpid()}.{uuid.uuid4().hex[:8]}"
                    try:
                        os.replace(lock_dir, steal)
                    except OSError:
                        # Someone else stole it or it was released — just retry acquire.
                        time.sleep(0.05)
                        continue
                    try:
                        for child in steal.iterdir():
                            child.unlink()
                        steal.rmdir()
                    except OSError:
                        pass
                    continue
            except OSError:
                pass
            if time.time() >= deadline:
                local.release()
                raise TimeoutError(f"Timeout waiting for lock: {lock_dir}")
            time.sleep(0.05)

    if not hasattr(_HELD_LOCKS, "keys"):
        _HELD_LOCKS.keys = set()
    _HELD_LOCKS.keys.add(clave)
    try:
        yield lock_dir
    finally:
        _HELD_LOCKS.keys.discard(clave)
        try:
            for child in lock_dir.iterdir():
                child.unlink()
            lock_dir.rmdir()
        except OSError:
            pass
        local.release()


# ── Escritura atómica ──────────────────────────────────────────────────────────


# Reexports históricos: el mecanismo tiene un solo owner en el paquete estable.


def guarda_secretos(path: Path, text: str) -> None:
    """Guarda lista para pasar en `guardas`: aborta si el texto lleva un secreto.

    Es la misma comprobación que `vault_io.atomic_write_text` hace desde v36, y
    está aquí para que un escritor que no quiere el resto de la política —el
    trace, por ejemplo— pueda conservar **ésta** sin arrastrar las otras cinco.
    Que el escaneo fuese inseparable del saneado y del ledger era parte de por
    qué el módulo de IO no se podía partir.

    Un escáner ausente no bloquea (`ImportError` → se deja pasar); un escáner
    **roto** tampoco, pero eso no se silencia aquí: quien llama decide si lo
    registra, y `vault_io` lo registra. Ver AP-37.
    """
    if not text or _env("VAULT_SKIP_SECRET_SCAN"):
        return
    try:
        from vault_secret_scan import vault_write_hook
    except ImportError:
        return
    ok, findings = vault_write_hook(text)
    if ok:
        return
    critical = [f for f in findings if f["severity"] == "critical"]
    details = "\n".join(
        f"  [{f['pattern_id']}] line {f['line_hint']}: {f['match_redacted']}"
        for f in critical[:5]
    )
    raise PermissionError(
        f"atomic_write_text blocked: {len(critical)} critical secret(s) "
        f"detected in content. Bypass with VAULT_SKIP_SECRET_SCAN=1.\n"
        f"{details}"
    )
