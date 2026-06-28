#!/usr/bin/env python3
"""Shared file IO helpers for vault tools."""

import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator

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
    """
    if env := os.environ.get("VAULT_ROOT"):
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
            return c
    # Accept any vault-* dir (fresh vault, nothing initialized yet)
    if candidates:
        return candidates[0]
    # Check if project_root itself IS a vault (scripts-inside-vault layout).
    # This is the case when the consumer has 00_System/01_Projects/etc. directly
    # under the same dir that contains scripts/ — common when a project ships
    # the spec file as a reference doc and the vault sits at the same level.
    marker_count = sum(1 for m in _VAULT_MARKERS if (project_root / m).exists())
    if marker_count >= 2:
        return project_root
    # Spec repo fallback: parent has vault-obsidian-architecture.md AND no
    # vault structure (i.e., this IS the spec repo, not a consumer vault).
    if (project_root / "vault-obsidian-architecture.md").exists():
        sandbox = project_root / "vault-sandbox"
        sandbox.mkdir(exist_ok=True)
        return sandbox
    return project_root


VAULT_ROOT: Path = _detect_vault_root()


@contextmanager
def file_lock(
    target: Path, timeout: float = 30.0, stale_after: float = 120.0
) -> Iterator[Path]:
    """Create an atomic directory lock near the target file.

    This avoids lost updates when multiple documentation tools update the same
    JSON index during mass generation. Stale locks are removed after
    ``stale_after`` seconds.
    """
    lock_root = target.parent / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_dir = lock_root / f"{target.name}.lock"
    deadline = time.time() + timeout

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
                    for child in lock_dir.iterdir():
                        child.unlink()
                    lock_dir.rmdir()
                    continue
            except OSError:
                pass
            if time.time() >= deadline:
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
    if path.suffix != ".md" or path.name == "index.md":
        return
    try:
        rel = path.relative_to(VAULT_ROOT)
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
