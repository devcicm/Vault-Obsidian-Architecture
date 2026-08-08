#!/usr/bin/env python3
"""Shared file IO helpers for vault tools."""

import copy
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from vault_encoding import (
    normalize_to_nfc,
    sanitize_content,
    strip_bom,
    decode_safely,
)

from vault_regex import (
    sanitize_wikilink_content,
    fix_nested_brackets,
    fix_whitespace_in_links,
    WIKILINK_MAX_LEN,
)

# La configuración se declara una vez y se lee por el registro, no con un
# `os.environ.get()` y un default por punto de uso. Ver `vault_entorno.py`
# para las trece variables y por qué estaban dispersas.
#
# El registro vive en `scripts/` y no en el paquete `vault/` porque un
# módulo de `scripts/` tiene que seguir funcionando **copiado suelto**: así
# se sincronizan los repos consumidores, y así lo comprueba
# `test_vault_containment`, que copia solo este fichero a un repo vacío.
# Colgarlo de `vault.kernel` lo rompía con un ModuleNotFoundError.
from vault_entorno import leer as _env


#: Origen de la detección del vault root — lo fija _detect_vault_root() y lo
#: consulta el guard AP-36. `repo_root_fallback` es el único valor de baja
#: confianza: significa que NO se encontró ningún vault y se está usando la raíz
#: del repo como si lo fuera (v39: causa histórica de 00_System/ y 99_Index/
#: generados fuera de todo vault-*).
_VAULT_ROOT_ORIGIN: str = "unknown"

#: Valores de _VAULT_ROOT_ORIGIN que NO identifican un vault real.
LOW_CONFIDENCE_ORIGINS = frozenset({"repo_root_fallback"})


def _detect_vault_root() -> Path:
    """Auto-detect vault root.

    Priority order:
    1. VAULT_ROOT env var (explicit override)
    2. vault-* subdirectory beside scripts/ (consumer repo layout):
       - First pass: prefer dirs that already have 00_System/, 99_Index/ or .obsidian
       - Second pass: accept any vault-* dir (fresh install, nothing initialized yet)
       vault-backups* AND vault-sandbox* dirs are excluded from both passes
       (vault-sandbox is a side-effect of the spec-repo fallback, not a real vault).
    3. scripts/ parent (scripts-inside-vault layout) IF it has vault structure
       (00_System/01_Projects/etc. directly under it). Previously this fallback
       only triggered when the parent had vault-obsidian-architecture.md, which
       caused a bug: any consumer vault that included the spec as a reference
       doc got misidentified as the spec repo and redirected to vault-sandbox/.
    4. Spec-repo sandbox: if the parent has vault-obsidian-architecture.md
       AND no vault structure markers, treat as spec repo and use vault-sandbox/.
    5. Último recurso: la raíz del repo. Marcada como `repo_root_fallback` —
       ver `vault_root_origin()`. Con VAULT_STRICT_ROOT=1 esto es un error en
       lugar de un silencio, porque es el caso en el que las tools escriben
       artefactos de vault fuera de cualquier vault.

    AP-36: esta función NO crea directorios. Antes hacía `sandbox.mkdir()` en
    la rama 4, y como VAULT_ROOT se evalúa a nivel de módulo, *importar*
    vault_io materializaba `vault-sandbox/` en cualquier repo que tuviera el
    manifiesto como doc de referencia. Los directorios se crean ahora en la
    primera escritura real (atomic_write_* ya hace mkdir del padre).
    """
    global _VAULT_ROOT_ORIGIN
    if env := _env("VAULT_ROOT"):
        _VAULT_ROOT_ORIGIN = "env"
        return Path(env).resolve()
    project_root = Path(__file__).parent.parent.resolve()
    _MARKERS = {"00_System", "99_Index", ".obsidian"}
    # Strong vault structure marker — at least 2 of these folders must exist
    # at the root level for the directory to be considered a vault.
    _VAULT_MARKERS = {
        "00_System",
        "01_Projects",
        "02_Observability",
        "03_Decisions",
        "99_Index",
        ".obsidian",
    }
    # Exclude vault-sandbox and *.bak from candidates — they're side-effects
    # of the spec-repo fallback or backups, not real vaults. Excluding them
    # prevents a chicken-and-egg situation where the old detection created
    # vault-sandbox/ and the new detection picks it as the vault because it
    # has 00_System.
    candidates = [
        s
        for s in sorted(project_root.iterdir())
        if s.is_dir()
        and (s.name.startswith("vault-") or s.name == "vault")
        and not s.name.startswith("vault-backups")
        and s.name != "vault-sandbox"
        and not s.name.endswith(".bak")
        # Un paquete Python no es un vault, aunque se llame `vault/`. La rama
        # "fresh" de abajo acepta un candidato por el NOMBRE, sin exigir un solo
        # marcador, así que crear el paquete `vault/` del refactor bastó para
        # que la autodetección dejara de devolver `vault-sandbox/` y empezara a
        # apuntar al código fuente — con origen `sibling_vault_dir_fresh`, es
        # decir, anunciando confianza. Es AP-44 en el detector: se validaba a sí
        # mismo por convención de nombre en vez de por el criterio del
        # consumidor, que es «¿tiene esto contenido de vault?».
        and not (s / "__init__.py").exists()
    ]
    # Prefer candidates that already have vault content (initialized vault)
    for c in candidates:
        if any((c / m).exists() for m in _MARKERS):
            _VAULT_ROOT_ORIGIN = "sibling_vault_dir"
            return c
    # Accept any vault-* dir (fresh vault, nothing initialized yet)
    if candidates:
        _VAULT_ROOT_ORIGIN = "sibling_vault_dir_fresh"
        return candidates[0]
    # Check if project_root itself IS a vault (scripts-inside-vault layout).
    # This is the case when the consumer has 00_System/01_Projects/etc. directly
    # under the same dir that contains scripts/ — common when a project ships
    # the spec file as a reference doc and the vault sits at the same level.
    marker_count = sum(1 for m in _VAULT_MARKERS if (project_root / m).exists())
    # 00_System/ and 99_Index/ are auto-created by the observability layer
    # (tool-trace, graph index) as a side-effect of running any tool, so their
    # presence alone must NOT qualify project_root as a vault — that creates a
    # self-reinforcing loop where one stray write makes the repo root the vault
    # forever. Require at least one CONTENT marker authored by a human/init.
    _CONTENT_MARKERS = {"01_Projects", "02_Observability", "03_Decisions", ".obsidian"}
    has_content = any((project_root / m).exists() for m in _CONTENT_MARKERS)
    if marker_count >= 2 and has_content:
        _VAULT_ROOT_ORIGIN = "scripts_inside_vault"
        return project_root
    # Spec repo fallback: parent has vault-obsidian-architecture.md AND no
    # vault structure (i.e., this IS the spec repo, not a consumer vault).
    # NO se crea el directorio aquí — ver docstring (AP-36).
    if (project_root / "vault-obsidian-architecture.md").exists():
        _VAULT_ROOT_ORIGIN = "spec_repo_sandbox"
        return project_root / "vault-sandbox"
    # Último recurso: no hay vault. Devolvemos la raíz del repo para no romper
    # los ~94 tools que no aceptan --root, pero queda marcado como baja
    # confianza para que el guard AP-36 lo denuncie en vez de silenciarlo.
    _VAULT_ROOT_ORIGIN = "repo_root_fallback"
    if _env("VAULT_STRICT_ROOT"):
        raise RuntimeError(
            f"No se encontró ningún vault desde {project_root}. Con VAULT_STRICT_ROOT=1 "
            "esto es un error: escribir aquí generaría 00_System/, 99_Index/ y demás "
            "artefactos fuera de todo vault. Crea un directorio 'vault-<nombre>/' o "
            "exporta VAULT_ROOT=<ruta del vault>."
        )
    return project_root


VAULT_ROOT: Path = _detect_vault_root()

#: El vault detectado al importar, guardado APARTE y nunca reescrito.
#:
#: `set_vault_root()` reancla las constantes de módulo derivadas del vault, y
#: `VAULT_ROOT` es una de ellas: se reapunta a sí misma. Sin esta copia, poner
#: el override a None no volvía al vault detectado —se quedaba en el último
#: destino para siempre— mientras `vault_root_origin()` seguía respondiendo
#: `spec_repo_sandbox`, es decir, anunciando confianza sobre una raíz que ya no
#: era ésa. Es AP-44 en el propio detector: certificaba con su criterio en vez
#: de con el del consumidor.
#: Se guarda como `str` y no como `Path` a propósito: `_reanclar_constantes()`
#: reapunta toda constante en mayúsculas cuyo valor sea un `Path` derivado del
#: vault, y esta copia lo es. Guardada como ruta, el reanclaje se la llevaba por
#: delante y el respaldo apuntaba al mismo sitio del que había que volver.
_VAULT_ROOT_DETECTADO: str = str(VAULT_ROOT)
_ORIGEN_DETECTADO: str = _VAULT_ROOT_ORIGIN


def vault_root_origin() -> str:
    """Qué regla de _detect_vault_root() eligió VAULT_ROOT.

    Valores: env | sibling_vault_dir | sibling_vault_dir_fresh |
    scripts_inside_vault | spec_repo_sandbox | repo_root_fallback |
    explicit_override.

    Con un override activo devuelve `explicit_override`: la raíz ya no la
    eligió ninguna regla de detección, y seguir citando la regla anterior sería
    atribuir a la autodetección una decisión que tomó quien llamó.
    """
    if _ACTIVE_VAULT_ROOT is not None:
        return "explicit_override"
    return _VAULT_ROOT_ORIGIN


def vault_root_is_confident() -> bool:
    """False cuando VAULT_ROOT es una suposición, no un vault identificado."""
    return _VAULT_ROOT_ORIGIN not in LOW_CONFIDENCE_ORIGINS

# ── Override en runtime (AP-36) ────────────────────────────────────────────────
# Los tools que aceptan --root deben llamar set_vault_root() ANTES de escribir,
# para que la capa de observabilidad (traces, tokens, locks) escriba en el vault
# objetivo y no en el VAULT_ROOT detectado en import. Los writers deben resolver
# la ruta vía get_vault_root() en tiempo de llamada, nunca como constante de módulo.
_ACTIVE_VAULT_ROOT: Optional[Path] = None


def _reanclar_constantes(anterior: Path, nueva: Path) -> List[str]:
    """Reapunta al vault nuevo las constantes de módulo derivadas del viejo.

    El problema que resuelve: 89 de 98 módulos hacen `from vault_io import
    VAULT_ROOT` y derivan sus rutas EN EL IMPORT (`CODE_DIR = VAULT_ROOT /
    "11_Code"`). Eso congela un `Path` literal, así que `set_vault_root()`
    cambiaba `get_vault_root()` y no cambiaba nada de lo que las tools usan de
    verdad para leer y escribir. Había dos verdades para "cuál es el vault", y
    la API pública de cambiarlo mentía: medido, `get_vault_root()` devolvía el
    vault nuevo mientras `vault_audit.VAULT_ROOT` seguía en el viejo.

    Reanclar es lo único que arregla el caso sin reescribir los 89 módulos:
    ningún proxy perezoso sobre `VAULT_ROOT` alcanzaría a las constantes ya
    derivadas de él. Se toca solo lo inequívoco —nombres en MAYÚSCULAS de
    módulos `vault_*` cuyo valor es un `Path` DENTRO de la raíz anterior—;
    cualquier otra cosa se deja como está.

    Devuelve los nombres reanclados, en `modulo.CONSTANTE`, para que la
    operación sea auditable en vez de mágica.
    """
    import sys as _sys

    tocados: List[str] = []
    for nombre_mod, modulo in list(_sys.modules.items()):
        if not nombre_mod.startswith("vault_") or modulo is None:
            continue
        for nombre, valor in list(vars(modulo).items()):
            if not nombre.isupper() or not isinstance(valor, Path):
                continue
            if nombre == "VAULT_ROOT":
                setattr(modulo, nombre, nueva)
                tocados.append(f"{nombre_mod}.{nombre}")
                continue
            try:
                relativa = valor.relative_to(anterior)
            except ValueError:
                continue  # no colgaba del vault: no es una ruta de vault
            setattr(modulo, nombre, nueva / relativa)
            tocados.append(f"{nombre_mod}.{nombre}")
    return tocados


#: Constantes reancladas por el último set_vault_root(). Auditable desde fuera.
_REANCLADAS: List[str] = []


def set_vault_root(path) -> Path:
    """Fija el vault activo para esta ejecución (override de la auto-detección).

    Además de fijar el override, reancla las constantes que los módulos ya
    importados derivaron del vault anterior — ver `_reanclar_constantes()`.
    """
    global _ACTIVE_VAULT_ROOT, _REANCLADAS
    anterior = get_vault_root().resolve()
    nueva = Path(path).resolve()
    _ACTIVE_VAULT_ROOT = nueva
    _REANCLADAS = _reanclar_constantes(anterior, nueva) if nueva != anterior else []
    return _ACTIVE_VAULT_ROOT


def rebound_constants() -> List[str]:
    """Constantes de módulo que el último set_vault_root() reapuntó."""
    return list(_REANCLADAS)


def reset_vault_root() -> Path:
    """Deshace el override y devuelve las constantes al vault detectado.

    Poner `_ACTIVE_VAULT_ROOT = None` a mano NO basta y ésa era la trampa: el
    reanclaje ya había reescrito `VAULT_ROOT` y las constantes de los módulos
    cargados, así que el proceso seguía apuntando al destino temporal. En una
    suite eso se ve como fallos que dependen del orden de los ficheros; en una
    tool, como escribir en el vault de la llamada anterior.
    """
    global _ACTIVE_VAULT_ROOT
    set_vault_root(Path(_VAULT_ROOT_DETECTADO))
    _ACTIVE_VAULT_ROOT = None
    return VAULT_ROOT


def get_vault_root() -> Path:
    """Vault root efectivo: el override de set_vault_root() o el auto-detectado."""
    return _ACTIVE_VAULT_ROOT if _ACTIVE_VAULT_ROOT is not None else VAULT_ROOT


# ── Rutas de ENTRADA del usuario (AP-36) ──────────────────────────────────────
# Distinto problema que el vault root: aquí la ruta apunta al proyecto que se
# documenta, no al vault. `Path.cwd()` no vale como ancla porque el CWD del
# proceso no es el del usuario: el runner MCP lanza las tools con cwd=scripts/,
# así que `--file src/foo.ts` resolvía a `scripts/src/foo.ts` y la tool leía un
# fichero que no existe o, peor, otro que sí.


def client_cwd() -> Path:
    """Directorio desde el que el usuario invocó, no desde el que corre Python.

    El runner MCP lo publica en `VAULT_CLIENT_CWD`. Sin esa variable —CLI
    directa— el CWD del proceso sí es el del usuario y vale.
    """
    declarado = _env("VAULT_CLIENT_CWD")
    if declarado:
        candidato = Path(declarado)
        if candidato.is_dir():
            return candidato.resolve()
    return Path.cwd()


def resolve_input_path(file_path) -> Path:
    """Ancla una ruta de entrada relativa contra client_cwd(). Absoluta: intacta."""
    p = Path(file_path)
    return p if p.is_absolute() else client_cwd() / p


# ── Contrato de tools (v39) ───────────────────────────────────────────────────
# El contrato vive DENTRO del vault: es un artefacto de datos del vault, no un
# archivo de las tools. Hasta v38.1 se escribía en scripts/tool-spec.json —
# fuera de todo vault y con write_text() no atómico.
TOOL_SPEC_NAME = "tool-spec.json"

#: Ubicación legacy (v33–v38.1). Se sigue LEYENDO para no romper vaults e
#: instalaciones que aún no han migrado — política de no-derogación. Nunca se
#: escribe aquí.
LEGACY_TOOL_SPEC = Path(__file__).resolve().parent / TOOL_SPEC_NAME


def tool_spec_path() -> Path:
    """Ruta canónica del contrato de tools: <vault>/00_System/tool-spec.json."""
    return get_vault_root() / "00_System" / TOOL_SPEC_NAME


def resolve_tool_spec() -> Optional[Path]:
    """Contrato existente a leer: el canónico si está, si no el legacy.

    Devuelve None si no existe en ninguna de las dos ubicaciones (los lectores
    ya tienen fallback a sus datos hardcodeados).
    """
    canonical = tool_spec_path()
    if canonical.exists():
        return canonical
    if LEGACY_TOOL_SPEC.exists():
        return LEGACY_TOOL_SPEC
    return None


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
                age = time.time() - lock_dir.stat().st_mtime
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


def assert_within_vault(path: Path, vault_root: Path) -> Path:
    """Resolve *path* and verify it stays inside *vault_root*.

    Protects against:
    - Absolute --folder args: Path("/vault") / "/etc" → "/etc" (pathlib replaces base)
    - Path traversal: --folder "../../outside"

    Returns the resolved absolute path on success; raises ValueError otherwise.
    """
    resolved = path.resolve()
    vault_resolved = vault_root.resolve()
    try:
        resolved.relative_to(vault_resolved)
    except ValueError:
        raise ValueError(
            f"Path '{path}' resolves to '{resolved}' which is outside "
            f"vault root '{vault_resolved}'. Use a relative path within the vault."
        )
    return resolved


# ────────────────────────────────────────────────────────────────────────────
# AP-37 — registro de escrituras
# ────────────────────────────────────────────────────────────────────────────
# El indicador de trabajo se MIDE donde el trabajo ocurre, no lo afirma cada
# tool en su return. Una tool que se limita a declarar `ok: true` está haciendo
# una afirmación no falsable; una que reporta `unchanged: 1` está diciendo algo
# comprobable — y es justo el caso que AP-37 nació para destapar (una migración
# que devolvía éxito habiendo aplicado cero cambios).
#
# El ledger es thread-local a propósito: la CLI consolidada ejecuta varias
# operaciones a la vez y un contador de módulo mezclaría el trabajo de unas con
# el de otras.
_write_ledger = threading.local()


def _ledger() -> Dict[str, int]:
    contadores = getattr(_write_ledger, "counts", None)
    if contadores is None:
        contadores = {"created": 0, "updated": 0, "unchanged": 0}
        _write_ledger.counts = contadores
    return contadores


def write_ledger_reset() -> None:
    """Pone el contador a cero. Lo llama `wrap_main` al arrancar cada tool."""
    _write_ledger.counts = {"created": 0, "updated": 0, "unchanged": 0}


def write_report() -> Dict[str, int]:
    """Qué escribió esta ejecución. Pensado para expandirse en el return de la tool.

    `written` es el total de archivos que cambiaron en disco: `unchanged` NO
    cuenta, porque reescribir un archivo con el mismo contenido no es trabajo.
    """
    c = dict(_ledger())
    c["written"] = c["created"] + c["updated"]
    return c


def record_raw_write(path: Path, text: str, encoding: str = "utf-8") -> str:
    """Registra una escritura que NO pasa por `atomic_write_text`, a propósito.

    Hay exactamente un motivo válido para escribir en crudo: `vault_section_index`
    genera índices con `Path.write_text` porque `atomic_write_text` dispara
    `_auto_section_index`, y el generador escribiéndose a sí mismo sería una
    recursión infinita. Esas escrituras son trabajo real y tienen que contar.

    Llamar a esto NO escribe: solo clasifica. Se invoca junto al `write_text`.
    """
    return _record_write(path, text, encoding)


#: Ficheros de telemetría interna que NO son trabajo de la tool. Escribir una
#: traza no es haber hecho nada por el vault, y contarla haría que el indicador
#: de AP-37 subiera con el número de errores registrados — justo al revés de lo
#: que mide. Se declaran por nombre porque viven en `00_System/`, que ya está
#: fuera de la cascada de índices por el mismo motivo.
_NO_ES_TRABAJO = frozenset({".tool-trace.json"})


def _record_write(path: Path, text: str, encoding: str) -> str:
    """Clasifica la escritura antes de hacerla. Nunca propaga errores."""
    if path.name in _NO_ES_TRABAJO:
        return "unchanged"
    try:
        if not path.exists():
            resultado = "created"
        else:
            resultado = (
                "unchanged"
                if path.read_text(encoding=encoding, errors="replace") == text
                else "updated"
            )
    except OSError:
        resultado = "updated"
    _ledger()[resultado] += 1
    return resultado


#: Fallos del escáner de secretos ocurridos en este proceso. En memoria además
#: de en disco: un test —y la propia tool— pueden preguntarlo sin leer ficheros.
_ESCANER_DEGRADADO: List[Dict[str, str]] = []

SCANNER_DEGRADED_LOG = "scanner-degraded.jsonl"


def _registrar_escaner_degradado(path: Path, exc: BaseException) -> None:
    """Deja constancia de que una escritura pasó sin escanear.

    Nunca levanta: si esto fallara, el remedio sería peor que la enfermedad.
    """
    entrada = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": str(path),
        "error": f"{type(exc).__name__}: {exc}",
    }
    _ESCANER_DEGRADADO.append(entrada)
    try:
        destino = get_vault_root() / "00_System" / SCANNER_DEGRADED_LOG
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Append directo a propósito: pasar por atomic_write_text aquí sería
        # recursión, y el registro tiene que sobrevivir justo al caso en que
        # el write path está roto.
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except Exception:
        pass  # el registro es best-effort; la lista en memoria ya lo tiene


def scanner_degradations() -> List[Dict[str, str]]:
    """Escrituras de este proceso que se hicieron sin escaneo de secretos."""
    return list(_ESCANER_DEGRADADO)


#: Nombres de dispositivo reservados de Windows. Un fichero llamado así no es un
#: fichero: `CON` es la consola, `NUL` el vacío, `COM1`/`LPT1` puertos. La
#: reserva ignora la extensión —`con.md` es `CON` igual— y no distingue
#: mayúsculas.
_NOMBRES_RESERVADOS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def _rechazar_nombre_reservado(path: Path) -> None:
    """Bloquea nombres que en Windows son dispositivos, no ficheros.

    Una nota titulada «CON», «Aux» o «Com1» produce por slug `con.md`, `aux.md`,
    `com1.md` — y ahí deja de haber fichero. Medido: `Path('con.md').exists()`
    devuelve `True` en un directorio vacío, `os.lstat` da `st_mode=S_IFCHR`, la
    escritura se va a la consola y **cualquier lectura se cuelga indefinidamente**
    esperando entrada. No falla: se queda. Es la peor forma de fallo que puede
    tener un vault, porque el proceso que lo abra no muere ni avisa.

    Se bloquea en el write path y no en el generador de slugs porque los slugs
    los generan 22 sitios y las escrituras pasan todas por aquí — el mismo
    reparto que AP-46. Se prohíbe el nombre, no el prefijo: `console.md` y
    `contrato.md` son ficheros perfectamente normales, y confundir «empieza por
    con» con «es CON» apagaría media sección de conceptos.

    Salió al ejecutar, no al leer: un test de durabilidad que llamó `con.md` a su
    fichero de control se colgó para siempre en vez de fallar (regla 7 en su
    forma más barata — el estándar se desarrolla en Windows y aun así nadie lo
    había escrito).
    """
    if path.stem.upper() in _NOMBRES_RESERVADOS:
        raise ValueError(
            f"atomic_write bloqueado: '{path.name}' usa el nombre de dispositivo "
            f"reservado '{path.stem.upper()}'. En Windows no sería un fichero sino "
            f"un dispositivo, y leerlo cuelga al proceso en vez de fallar. Renombra "
            f"la nota (p. ej. '{path.stem}-nota{path.suffix}')."
        )


def _rechazar_traversal(path: Path) -> None:
    """Bloquea la escritura si la ruta SALE del vault por `..`.

    `assert_within_vault()` existe desde v28, pero es el llamante quien tiene
    que acordarse de invocarla, y trece módulos que escriben no lo hacían. Aquí
    la comprobación es del propio write path, así que no depende de la memoria
    de nadie.

    Lo que se prohíbe es el traversal —el `..` que trepa por encima de la raíz,
    que es el vector real de AP-36—. NO se exige que toda escritura caiga bajo
    `get_vault_root()`: hay escrituras legítimas contra otro vault (tests con
    raíz temporal, tools con `--root`, migraciones entre vaults), y confundir
    "otro vault" con "fuera del vault" convertiría el guard en ruido.
    """
    if ".." not in path.parts:
        return
    raiz = get_vault_root().resolve()
    resuelta = path.resolve()
    try:
        resuelta.relative_to(raiz)
    except ValueError:
        raise ValueError(
            f"atomic_write bloqueado: '{path}' resuelve a '{resuelta}', fuera del "
            f"vault '{raiz}'. Las rutas se derivan de get_vault_root(), nunca por "
            f"concatenación de un argumento del usuario (AP-36)."
        )


#: Notas escritas en este proceso cuyo frontmatter parsea pero sale sin `type:`.
#: No se bloquea —hay notas legítimas sin tipo y romper el estándar entero por
#: eso sería peor—, pero deja de ser invisible (AP-46).
_FRONTMATTER_SIN_TIPO: List[Dict[str, str]] = []

#: Rutas donde un frontmatter roto es el dato, no el defecto: copias, historia y
#: cuarentena guardan justamente lo que vino mal para poder repararlo después.
_SIN_GUARD_FRONTMATTER = frozenset({"vault-backups", ".history", "20_Quarantine"})


def frontmatter_degradations() -> List[Dict[str, str]]:
    """Notas escritas en este proceso con frontmatter válido pero sin `type:`."""
    return list(_FRONTMATTER_SIN_TIPO)


def _verificar_frontmatter(path: Path, text: str) -> None:
    """Relee el frontmatter que se va a escribir, con el criterio del consumidor.

    AP-46: veintiséis tools montan el bloque concatenando líneas y ninguna
    comprueba el resultado. El fallo no se ve al escribir —la tool devuelve
    `ok: true` porque el fichero se creó— sino al auditar, cuando la nota ya es
    el dato. `vault_migrate_docs` cortaba el documento por la línea 7 y llevaba
    versiones publicándose con el bloque sin cerrar.

    Verificar aquí alcanza a las 26 tools sin tocar ninguna, y la adopción de
    `vault_write` puede seguir siendo gradual. Se valida con `yaml.safe_load`
    —lo que usa quien lo lee— y no con un regex por líneas (AP-44).

    Bloquea solo lo que nunca es intencional: abrir `---` y no cerrarlo, o un
    bloque que no parsea. La ausencia de `type:` se registra sin bloquear.
    """
    if path.suffix.lower() != ".md" or not text.startswith("---"):
        return
    if _SIN_GUARD_FRONTMATTER & set(path.parts):
        return

    cuerpo = text.split("\n", 1)[1] if "\n" in text else ""
    cierre = cuerpo.find("\n---")
    if cierre == -1 and not cuerpo.startswith("---"):
        raise ValueError(
            f"atomic_write bloqueado: '{path.name}' abre frontmatter con '---' y "
            f"nunca lo cierra. El bloque se construyó a mano y nadie releyó el "
            f"resultado (AP-46)."
        )
    bruto = cuerpo[: cierre + 1] if cierre != -1 else ""

    try:
        import yaml
    except ImportError:
        return
    try:
        datos = yaml.safe_load(bruto)
    except Exception as exc:
        raise ValueError(
            f"atomic_write bloqueado: el frontmatter de '{path.name}' no parsea "
            f"como YAML ({type(exc).__name__}: {exc}). Es lo que verá quien lea la "
            f"nota, no lo que creyó escribir la tool (AP-46)."
        )
    if isinstance(datos, dict) and not datos.get("type"):
        _FRONTMATTER_SIN_TIPO.append({"path": str(path), "reason": "missing_type"})


def _escribir_temporal(temp: Path, text: str, encoding: str) -> None:
    """Escribe el temporal y, si `VAULT_FSYNC=1`, lo vuelca a disco.

    El volcado va **dentro** del `with`, sobre el descriptor con el que se
    escribió: en Windows `os.fsync` sobre un `os.open(..., O_RDONLY)` falla con
    `Bad file descriptor` —`_commit` exige acceso de escritura—, así que
    sincronizar «después, reabriendo» funciona en POSIX y rompe en la plataforma
    donde se desarrolla este repo. Se descubrió al ejecutarlo, no al leerlo.

    `newline` queda por defecto a propósito: es lo que hacía `Path.write_text`, y
    cambiarlo alteraría los saltos de línea de cada nota del estándar. La palanca
    es de durabilidad, no de contenido.
    """
    import os

    with open(temp, "w", encoding=encoding) as fh:
        fh.write(text)
        if _env("VAULT_FSYNC"):
            fh.flush()
            os.fsync(fh.fileno())


def _fsync_si_procede(temp: Path) -> None:
    """Vuelca el directorio padre si `VAULT_FSYNC=1`, para que el rename dure.

    Aquí está la **decisión** de durabilidad del estándar; el volcado del
    contenido lo hace `_escribir_temporal` sobre su propio descriptor.

    **La durabilidad del estándar es la del sistema de ficheros, y eso es una
    decisión, no un olvido.** `atomic_write_text` da atomicidad —temp + `os.replace`,
    nadie ve la nota a medias— pero no durabilidad: entre el `replace` y el
    volcado real hay una ventana en la que un corte de corriente deja la nota
    truncada o vacía. Cerrarla por defecto cuesta un `fsync` por escritura, y hay
    tools que escriben cientos de ficheros en una pasada (`vault_reindex`,
    `vault_onboard`, `vault_migrate_docs`): el coste es del orden de milisegundos
    por nota sobre discos que no lo agregan.

    El reparto elegido: **por defecto no**, porque el contenido de un vault es
    reconstruible —está en git, en el proyecto de origen o en los `vault-backups/`—
    y perder la última escritura ante un corte es un daño acotado. **Opt-in con
    `VAULT_FSYNC=1`** para quien escriba sobre almacenamiento volátil o en un
    entorno donde el corte sea plausible.

    Se sincroniza además el directorio padre en POSIX: sin eso, el `rename` puede
    no haber llegado a disco aunque el contenido sí, y el fichero reaparecería con
    el nombre viejo. En Windows no existe descriptor de directorio y `os.replace`
    ya es atómico a nivel de metadatos, así que ese paso se omite —callando, que
    es lo correcto aquí: no es una degradación, es que no aplica—.
    """
    import os

    if not _env("VAULT_FSYNC"):
        return
    if hasattr(os, "O_DIRECTORY"):
        dir_fd = os.open(str(temp.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def atomic_write_text(
    path: Path, text: str, encoding: str = "utf-8", sanitize: bool = True
) -> None:
    """Write text to file with optional encoding sanitization.

    Args:
        path: Destination file path
        text: Content to write
        encoding: Text encoding (default: utf-8)
        sanitize: If True, applies encoding sanitization (default: True)

    v36: Pre-write secret scan (I1/I5 fix). If text contains critical
    secrets (AWS keys, GitHub tokens, bearer tokens, private keys), the
    write is aborted with a descriptive error. Set env var
    VAULT_SKIP_SECRET_SCAN=1 to bypass (not recommended).
    """
    import os

    if text and not _env("VAULT_SKIP_SECRET_SCAN"):
        try:
            from vault_secret_scan import vault_write_hook, has_blocking_findings

            ok, findings = vault_write_hook(text)
            if not ok:
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
        except ImportError:
            pass  # vault_secret_scan not available — skip
        except PermissionError:
            raise
        except Exception as exc:
            # No se bloquea la escritura por un fallo del escáner —eso
            # convertiría un bug del guard en una caída del estándar entero—,
            # pero un escáner roto dejaba de proteger sin que nadie se enterara.
            # Queda registrado para que `vault_audit` lo vea (AP-37: el fallo
            # silencioso se cuenta como éxito).
            _registrar_escaner_degradado(path, exc)

    _rechazar_traversal(path)
    _rechazar_nombre_reservado(path)
    _verificar_frontmatter(path, text or "")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Apply encoding sanitization if enabled
    if sanitize and text:
        # Strip BOM if present
        text, had_bom = strip_bom(text)

        # Apply full sanitization pipeline (auto-fix mode)
        text, fixes = sanitize_content(text, dry_run=False)

        # Log fixes if any were applied (for debugging)
        if fixes:
            try:
                from vault_encoding import log_encoding_fixes

                log_encoding_fixes(fixes, path, "atomic_write_text")
            except Exception:
                pass  # Don't fail writing if logging fails

    # Short temp name avoids Windows MAX_PATH (260 chars) on deep vault paths.
    # v36: wrap write+replace in try/except so the temp file is cleaned up
    # if write_text fails (disk full, permissions, encoding). Without this,
    # repeated failures leave .tmp.<pid>.<hex> orphans accumulating in
    # path.parent, which is a slow disk-fill risk.
    # Se clasifica con el texto YA saneado: comparar contra el original daría
    # `updated` en escrituras que el saneado deja idénticas.
    _record_write(path, text, encoding)

    temp = path.parent / f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    try:
        _escribir_temporal(temp, text, encoding)
        _fsync_si_procede(temp)
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    _auto_section_index(path)

    _auto_tag_ledger(path, text)


# Carpetas que no disparan la cascada de índices. Son dos cosas distintas y
# conviene no mezclarlas: las dos secciones canónicas que gestionan su propio
# índice, y todo lo que ni siquiera es una sección — eso último lo declara
# `vault_registry.NON_SECTION_ROOT_FOLDERS`, que es también lo que el audit
# consulta para CN-02. Tenerlo copiado aquí fue como `docs/` acabó siendo
# invisible para el kernel y una violación para el audit (AP-05).
_SECCIONES_CON_INDICE_PROPIO = frozenset({"00_System", "99_Index"})


def _skip_auto_index() -> frozenset:
    from vault_registry import NON_SECTION_ROOT_FOLDERS  # lazy: registro sin deps

    return _SECCIONES_CON_INDICE_PROPIO | frozenset(NON_SECTION_ROOT_FOLDERS)


_SKIP_AUTO_INDEX = _skip_auto_index()


def _auto_section_index(path: Path) -> None:
    """Auto-trigger section index update after writing any vault .md note.

    Called internally by atomic_write_text. Covers all tools without requiring
    each one to explicitly call update_section_index — single responsibility point.

    Skips: non-.md files, index.md itself, system/index sections, paths outside vault.
    Uses lazy import to avoid circular dependency with vault_section_index.
    """
    if path.suffix != ".md":
        return
    try:
        rel = path.relative_to(get_vault_root())
    except ValueError:
        return  # path outside vault root
    parts = rel.parts
    if len(parts) < 2:
        return
    section = parts[0]
    if section in _SKIP_AUTO_INDEX:
        return
    try:
        from vault_section_index import (
            vault_section_index,
        )  # lazy — avoids circular import

        # Self-healing: si lo escrito ES un index.md (un agente lo generó a
        # mano, posiblemente con [[stem|alias]] en las celdas — formato
        # prohibido), regeneramos el índice canónico encima. Sin recursión:
        # el generador escribe via Path.write_text, no via atomic_write_text.
        vault_section_index(section)
    except Exception:
        pass  # index failure must never block the write that triggered it


def _auto_tag_ledger(path: Path, text: str) -> None:
    """Anota en la bitácora de vocabulario los tags de la nota recién escrita.

    AP-39 dice que un tag nuevo se admite **pero se registra**, y hasta ahora lo
    registraba un solo escritor: `vault_write`. Los catorce `*_save` que llevan
    tags construyen su frontmatter y llaman directamente a `atomic_write_text`,
    así que la norma se cumplía en una de cada quince escrituras. El término
    entraba en el vault, la bitácora no se enteraba, y el audit lo denunciaba
    después contra la nota — culpando al contenido de un fallo del escritor. Es
    AP-43 en su forma literal: norma sin refuerzo en el punto de uso.

    Va aquí y no en cada tool por lo mismo que `_auto_section_index`: este es el
    único punto por el que pasan todas las escrituras. Ponerlo en los catorce
    sitios funciona hasta que alguien escribe el decimoquinto.

    Nunca levanta ni bloquea: la bitácora es memoria, no un guard. Si falla, la
    escritura ya es válida y el audit de AP-39 recoge el término más tarde.
    """
    if path.suffix != ".md" or not text.startswith("---"):
        return
    try:
        rel = str(path.relative_to(get_vault_root())).replace("\\", "/")
    except ValueError:
        return  # fuera del vault: no es una nota
    if rel.split("/")[0] in _SKIP_AUTO_INDEX:
        return
    try:
        from vault_tags import (  # lazy — evita el ciclo con el kernel
            _parse_frontmatter_tags,
            registrar_tags_de_nota,
        )

        registrar_tags_de_nota(_parse_frontmatter_tags(text), rel)
    except Exception:
        pass


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    atomic_write_text(
        path, json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@contextmanager
def indice_compartido(path: Path, vacio: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Lee un índice compartido, deja mutarlo y lo devuelve al disco, bajo lock.

    `atomic_write_json` garantiza que el fichero nunca queda a medias, y **no
    hace nada** contra el problema real de estos índices, que es otro: cinco
    `*_save` hacían `load_index()` → mutar → `atomic_write_json()` sin lock.
    Dos guardados concurrentes leen el mismo índice, cada uno añade su entrada,
    gana el segundo, y la primera desaparece — con las dos tools devolviendo
    `ok: true`. Es AP-37 por la puerta de atrás: trabajo perdido reportado como
    éxito.

    La otra mitad es peor y por eso el lock abarca **desde la lectura hasta la
    escritura**, no solo la escritura: tres de esos índices son además el
    contador del correlativo (`len(index["bugs"]) + 1`). Reservar el número
    fuera del lock hace que dos guardados obtengan `REQ-001` los dos, escriban
    el mismo nombre de fichero y uno pise al otro. El número tiene que salir
    del mismo tramo exclusivo que lo consume.

    `vacio` es lo que se devuelve cuando el índice no existe todavía. Se copia
    en profundidad: si se cediera el mismo objeto, dos llamadas sobre un vault
    recién creado compartirían la lista y la segunda vería las entradas de la
    primera.

    **Solo escribe si algo cambió.** Tres de los cinco tienen un `return`
    temprano dentro de la región —rutas de error como `INVALID_PATH`— que hoy
    no tocan el índice. Un `with` sale por ahí de forma normal, así que la
    escritura se ejecutaría igualmente y el camino de fallo pasaría a tener un
    side-effect que no tenía, contado además por `write_report()`. Comparar
    antes de escribir es más barato que pedirle a cinco puntos de uso que se
    acuerden de confirmar, y deja la regla donde se puede comprobar: si no
    cambió nada, no se escribe nada (AP-36, AP-37).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout=30.0):
        try:
            datos = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            datos = copy.deepcopy(vacio)
        antes = json.dumps(datos, sort_keys=True, ensure_ascii=False)
        yield datos
        if json.dumps(datos, sort_keys=True, ensure_ascii=False) != antes:
            atomic_write_json(path, datos)


def safe_wikilink(text: str) -> str:
    """Sanitize text for safe use inside [[...]] wiki-links (AP-22 guard).

    Sanitization steps:
    1. Fix nested brackets: [[[[ -> [[
    2. Fix whitespace: [[  note  ]] -> [[note]]
    3. Validate length (max WIKILINK_MAX_LEN chars)
    4. Remove brackets, pipe, newlines, quotes, backslashes
    5. Collapse multiple dashes
    6. Strip leading/trailing dashes

    Returns a safe fallback if result is empty.

    Raises:
        ValueError: If result exceeds max length after sanitization.
    """
    if not text or not text.strip():
        return "nota-sin-titulo"

    sanitized = text.strip()

    # Step 1: Fix nested brackets
    sanitized = fix_nested_brackets(sanitized)

    # Step 2: Fix whitespace inside links
    sanitized = fix_whitespace_in_links(sanitized)

    # Step 3: Validate length BEFORE removing characters (length is about content)
    if len(sanitized) > WIKILINK_MAX_LEN:
        # Try to sanitize first, then check again
        pass

    # Step 4: Remove brackets, pipe, newlines, quotes, backslashes
    sanitized = re.sub(r'[\[\]\|\n\r"\\]', "", sanitized)

    # Step 5: Collapse multiple spaces to single space
    sanitized = re.sub(r"[\s]+", " ", sanitized)

    # Step 6: Collapse multiple dashes and strip
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")

    # Step 7: Final strip
    sanitized = sanitized.strip()

    # Validate length after all processing
    if len(sanitized) > WIKILINK_MAX_LEN:
        sanitized = sanitized[:WIKILINK_MAX_LEN]

    return sanitized or "nota-sin-titulo"


def normalize_stem(s: str) -> str:
    """Canonical form for fuzzy stem comparison (vault_write + vault_audit).

    Strips case, dashes, underscores, spaces, dots, and the .md suffix.
    Used to detect whether a wiki-link target actually exists anywhere in
    the vault regardless of how it was written (kebab-case, snake_case, spaces).

    Examples:
        normalize_stem("Mi Proyecto Demo")   -> "miproyectodemo"
        normalize_stem("mi-proyecto-demo.md") -> "miproyectodemo"
        normalize_stem("mi_proyecto_demo")    -> "miproyectodemo"
        normalize_stem("Índice")              -> "indice"

    Los acentos se pliegan porque `slugify` translitera al derivar el nombre de
    fichero: sin plegarlos aquí, `Índice.md` (escrita antes) e `indice.md` (la
    que se derivaría hoy) parecerían dos notas distintas y el vault acabaría con
    las dos. El criterio de comparación tiene que ser el del consumidor, no el
    de quien escribe (AP-44).
    """
    from vault_lib import fold_accents

    return (
        fold_accents(s)
        .lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace(".", "")
        .removesuffix("md")
    )


def update_section_index(folder: str) -> None:
    """Regenerate section index without silently discarding errors.

    Calls vault_section_index and logs failures to the trace log instead of
    swallowing them with bare except/pass. Safe to call from any tool.
    """
    try:
        from vault_section_index import vault_section_index  # type: ignore

        vault_section_index(folder)
    except Exception as exc:
        try:
            from vault_errors import emit_error  # type: ignore

            emit_error(
                "update_section_index",
                "UNEXPECTED_ERROR",
                f"Failed to update index for {folder}: {exc}",
            )
        except Exception:
            pass  # logging failure must never crash the caller


def atomic_update_json(
    path: Path,
    default: Dict[str, Any],
    update: Callable[[Dict[str, Any]], Dict[str, Any]],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    with file_lock(path, timeout=timeout):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = dict(default)
        except (FileNotFoundError, json.JSONDecodeError):
            data = dict(default)
        updated = update(data)
        atomic_write_json(path, updated)
        return updated


#: Directorios cuyo contenido es una INSTANTÁNEA congelada, no una nota viva.
#: AP-36 obliga a que los side-effects (backups, papelera, historial) vivan
#: DENTRO del vault. Sin excluirlos, toda tool que barre `rglob("*.md")` se
#: audita a sí misma: en el vault de BuilderX eran 194 de 216 violaciones de
#: `vault_norms` (90%) y 46 de 69 errores Mermaid (67%), todas en copias de
#: seguridad. No es solo ruido en la métrica — manda al agente a "corregir" una
#: instantánea, que es exactamente lo que destruye su valor como backup. Una
#: violación dentro de un backup ya se reportó cuando la nota estaba viva.
#:
#: Vive aquí, y no en la tool que lo descubrió, porque el criterio de "qué es
#: una nota viva" es del vault, no de un barrido concreto.
SNAPSHOT_DIRS = ("vault-backups", ".trash", ".history")


def is_snapshot_path(rel: "str | Path") -> bool:
    """True si la ruta cae dentro de una instantánea congelada.

    Compara segmento a segmento — un `in` sobre la cadena daría falso positivo
    en una nota legítima como `07_Knowledge/concepts/como-usar-vault-backups.md`.
    Acepta separador de Windows porque las rutas relativas llegan de `os.path`.
    """
    partes = str(rel).replace("\\", "/").split("/")
    return any(p in SNAPSHOT_DIRS for p in partes)
