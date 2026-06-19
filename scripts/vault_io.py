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


def _detect_vault_root() -> Path:
    """Auto-detect vault root.

    Priority order:
    1. VAULT_ROOT env var (explicit override)
    2. vault-* subdirectory beside scripts/ (consumer repo layout):
       - First pass: prefer dirs that already have 00_System/, 99_Index/ or .obsidian/
       - Second pass: accept any vault-* dir (fresh install, nothing initialized yet)
       vault-backups* dirs are excluded from both passes.
    3. Parent of scripts/ directory (scripts-inside-vault layout, source repo)
    """
    if env := os.environ.get("VAULT_ROOT"):
        return Path(env).resolve()
    project_root = Path(__file__).parent.parent.resolve()
    _MARKERS = {"00_System", "99_Index", ".obsidian"}
    candidates = [
        s for s in sorted(project_root.iterdir())
        if s.is_dir() and s.name.startswith("vault-") and not s.name.startswith("vault-backups")
    ]
    # Prefer candidates that already have vault content (initialized vault)
    for c in candidates:
        if any((c / m).exists() for m in _MARKERS):
            return c
    # Accept any vault-* dir (fresh vault, nothing initialized yet)
    if candidates:
        return candidates[0]
    # Last resort fallback: parent.parent.
    # If that path is the spec repo (has vault-obsidian-architecture.md),
    # redirect vault content to vault-sandbox/ to avoid polluting the spec root.
    if (project_root / "vault-obsidian-architecture.md").exists():
        sandbox = project_root / "vault-sandbox"
        sandbox.mkdir(exist_ok=True)
        return sandbox
    return project_root


VAULT_ROOT: Path = _detect_vault_root()


@contextmanager
def file_lock(target: Path, timeout: float = 30.0, stale_after: float = 120.0) -> Iterator[Path]:
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


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Short temp name avoids Windows MAX_PATH (260 chars) on deep vault paths
    temp = path.parent / f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    temp.write_text(text, encoding=encoding)
    os.replace(temp, path)
    _auto_section_index(path)


# Sections that manage their own indexes — skip auto-trigger for these
_SKIP_AUTO_INDEX = frozenset({"00_System", "99_Index", ".history", "vault-backups"})


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
        from vault_section_index import vault_section_index  # lazy — avoids circular import
        vault_section_index(section)
    except Exception:
        pass  # index failure must never block the write that triggered it


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_wikilink(text: str) -> str:
    """Sanitize text for safe use inside [[...]] wiki-links (AP-22 guard).

    Removes or replaces characters that break Obsidian wiki-link syntax:
    [ ] | newlines backslash quotes. Returns a safe fallback if result is empty.
    """
    if not text or not text.strip():
        return "nota-sin-titulo"
    sanitized = re.sub(r'[\[\]\|\n\r"\\]', '-', text.strip())
    sanitized = re.sub(r'-{2,}', '-', sanitized).strip('-')
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
    return s.lower().replace("-", "").replace("_", "").replace(" ", "").replace(".", "").removesuffix("md")


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
            emit_error("update_section_index", "UNEXPECTED_ERROR",
                       f"Failed to update index for {folder}: {exc}")
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
