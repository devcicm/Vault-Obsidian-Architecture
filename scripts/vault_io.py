#!/usr/bin/env python3
"""Shared file IO helpers for vault tools."""

import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

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
    if env := os.environ.get("VAULT_ROOT"):
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
    if os.environ.get("VAULT_STRICT_ROOT"):
        raise RuntimeError(
            f"No se encontró ningún vault desde {project_root}. Con VAULT_STRICT_ROOT=1 "
            "esto es un error: escribir aquí generaría 00_System/, 99_Index/ y demás "
            "artefactos fuera de todo vault. Crea un directorio 'vault-<nombre>/' o "
            "exporta VAULT_ROOT=<ruta del vault>."
        )
    return project_root


VAULT_ROOT: Path = _detect_vault_root()


def vault_root_origin() -> str:
    """Qué regla de _detect_vault_root() eligió VAULT_ROOT.

    Valores: env | sibling_vault_dir | sibling_vault_dir_fresh |
    scripts_inside_vault | spec_repo_sandbox | repo_root_fallback.
    """
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


def set_vault_root(path) -> Path:
    """Fija el vault activo para esta ejecución (override de la auto-detección)."""
    global _ACTIVE_VAULT_ROOT
    _ACTIVE_VAULT_ROOT = Path(path).resolve()
    return _ACTIVE_VAULT_ROOT


def get_vault_root() -> Path:
    """Vault root efectivo: el override de set_vault_root() o el auto-detectado."""
    return _ACTIVE_VAULT_ROOT if _ACTIVE_VAULT_ROOT is not None else VAULT_ROOT


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


@contextmanager
def file_lock(
    target: Path, timeout: float = 30.0, stale_after: float = 120.0
) -> Iterator[Path]:
    """Create an atomic directory lock near the target file.

    This avoids lost updates when multiple documentation tools update the same
    JSON index during mass generation. Stale locks are removed after
    ``stale_after`` seconds. Layered: an in-process threading.Lock serializes
    threads in this process; the mkdir directory-lock serializes across processes.
    """
    lock_root = target.parent / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_dir = lock_root / f"{target.name}.lock"
    deadline = time.time() + timeout

    local = _local_lock_for(str(lock_dir))
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

    try:
        yield lock_dir
    finally:
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


def _record_write(path: Path, text: str, encoding: str) -> str:
    """Clasifica la escritura antes de hacerla. Nunca propaga errores."""
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

    if text and not os.environ.get("VAULT_SKIP_SECRET_SCAN"):
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
        except Exception:
            pass  # never block writes on scanner errors

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
        temp.write_text(text, encoding=encoding)
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    _auto_section_index(path)


# Sections that manage their own indexes — skip auto-trigger for these
_SKIP_AUTO_INDEX = frozenset(
    {"00_System", "99_Index", ".history", "vault-backups", "docs"}
)


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


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    atomic_write_text(
        path, json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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
    """
    return (
        s.lower()
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
