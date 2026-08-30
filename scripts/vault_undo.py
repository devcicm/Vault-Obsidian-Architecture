#!/usr/bin/env python3
"""
Vault Undo Tool — Recover a note from .history/.

Lists available versions in .history/ and restores one to the vault.
Does NOT overwrite the current version — restores to a new file unless --force is used.

SP-01 applies if the restored note replaces an existing one: a change_log entry
with action=updated is written before the restore.

Usage:
    python vault_undo.py --list "01_Projects/ans/status.md"
    python vault_undo.py --restore "01_Projects/ans/status.md"
    python vault_undo.py --restore "01_Projects/ans/status.md" --version "01_Projects__ans__status-2026-07-15T09-00-00.md"
    python vault_undo.py --restore "01_Projects/ans/status.md" --force   # overwrite current
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, emit_fallo, wrap_main
from vault_io import atomic_write_text
from vault_lib import utcnow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    return RepositorioAutoria(construir(root))


def _history_dir() -> Path:
    return _repo().dir_historial


def get_history_versions(note_path: str) -> List[Dict[str, Any]]:
    """Return sorted list of version metadata for a note (newest first)."""
    history_dir = _history_dir()
    if not history_dir.exists():
        return []

    note_path_obj = _raiz() / note_path
    if not note_path_obj.exists():
        return []

    folder = str(note_path_obj.parent.relative_to(_raiz())).replace("\\", "/")
    stem = note_path_obj.stem

    folder_prefix = folder.replace("/", "__")
    prefix = f"{folder_prefix}__{stem}-"

    versions: List[Dict[str, Any]] = []
    for f in history_dir.iterdir():
        if not f.is_file() or not f.name.startswith(prefix):
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        versions.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "modified": mtime.isoformat(),
        })

    versions.sort(key=lambda x: x["modified"], reverse=True)
    return versions


def _restore_change_log(note_path: str, version_filename: str, agent: str) -> str:
    """Write SP-01 entry before restoring over an existing note. Returns entry id."""
    from vault_change_log import vault_change_log_add

    result = vault_change_log_add(
        action="updated",
        path=note_path,
        reason=f"Restored from .history/{version_filename}",
        agent=agent,
    )
    if not result.get("ok"):
        raise RuntimeError(f"vault_change_log_add failed: {result}")
    return result["id"]


def vault_undo(
    path: str,
    version: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    agent: str = "claude",
) -> Dict[str, Any]:
    """
    Restore a note from .history/.

    By default restores to a NEW file: <note>-restored-<timestamp>.md
    With --force: overwrites the current note (SP-01 change_log entry is written).

    Args:
        path: vault-relative note path
        version: specific version filename in .history/ (default: most recent)
        force: overwrite current note instead of creating restored copy
        dry_run: don't write anything, just report what would happen
        agent: agent name for change_log
    """
    vault_root = _raiz()
    note_path = vault_root / path

    if not note_path.exists():
        return emit_error(
            "vault_undo", "NOTE_NOT_FOUND",
            f"No existe la nota: {path}",
        )

    versions = get_history_versions(path)
    if not versions:
        return emit_error(
            "vault_undo", "HISTORY_NOT_FOUND",
            f"No se encontraron versiones en .history/ para: {path}",
        )

    if version is None:
        target = versions[0]
    else:
        target = next((v for v in versions if v["filename"] == version), None)
        if target is None:
            available = [v["filename"] for v in versions]
            return emit_error(
                "vault_undo", "VERSION_NOT_FOUND",
                f"Version '{version}' no encontrada. Disponibles: {available}",
            )

    history_file = _history_dir() / target["filename"]
    restored_content = history_file.read_text(encoding="utf-8", errors="replace")

    if force:
        if not dry_run:
            _restore_change_log(path, target["filename"], agent)
            atomic_write_text(note_path, restored_content)
        return {
            "ok": True,
            "action": "overwritten",
            "note": path,
            "restored_from": target["filename"],
            "restored_at": utcnow(),
            "versions_restored": 1,
            "dry_run": dry_run,
        }
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        stem = note_path.stem
        restored_name = f"{stem}-restored-{timestamp}.md"
        restored_path = note_path.parent / restored_name

        if not dry_run:
            _restore_change_log(path, target["filename"], agent)
            atomic_write_text(restored_path, restored_content)

        return {
            "ok": True,
            "action": "restored_as_new",
            "note": path,
            "restored_from": target["filename"],
            "restored_to": str(restored_path.relative_to(vault_root)).replace("\\", "/"),
            "restored_at": utcnow(),
            "versions_restored": 1,
            "dry_run": dry_run,
        }


def vault_undo_list(path: str) -> Dict[str, Any]:
    """List available versions in .history/ for a note."""
    versions = get_history_versions(path)
    if not versions:
        return emit_error(
            "vault_undo", "HISTORY_NOT_FOUND",
            f"No se encontraron versiones en .history/ para: {path}",
        )
    return {
        "ok": True,
        "note": path,
        "versions": versions,
        "total": len(versions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Undo — recover notes from .history/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Listar versiones disponibles
  python vault_undo.py --list "01_Projects/ans/status.md"

  # Restaurar la version mas reciente como nuevo archivo
  python vault_undo.py --restore "01_Projects/ans/status.md"

  # Restaurar version especifica como nuevo archivo
  python vault_undo.py --restore "01_Projects/ans/status.md" --version "01_Projects__ans__status-2026-07-15T09-00-00.md"

  # Restaurar sobreescribiendo la nota actual (SP-01: genera change_log)
  python vault_undo.py --restore "01_Projects/ans/status.md" --force

  # Simular sin escribir nada
  python vault_undo.py --restore "01_Projects/ans/status.md" --dry-run

Notas:
  - Sin --force: restaura como <nota>-restored-<timestamp>.md (no sobreescribe)
  - Con --force: sobreescribe la nota actual y escribe entrada en change-log (SP-01)
  - Solo funciona para notas que fueron editadas con vault_write (que crea el .history/)
""",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", dest="list_path", metavar="PATH",
                       help="Listar versiones disponibles en .history/ para esta nota")
    group.add_argument("--restore", dest="restore_path", metavar="PATH",
                       help="Restaurar una version desde .history/")

    parser.add_argument("--version", dest="version",
                        help="Filename exacto en .history/ (default: la mas reciente)")
    parser.add_argument("--force", action="store_true",
                        help="Sobrescribir la nota actual en lugar de crear copia")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo reportar lo que haria, sin escribir nada")
    parser.add_argument("--agent", default="claude",
                        help="Nombre del agente para change-log (default: claude)")

    args = parser.parse_args()

    if args.list_path:
        result = vault_undo_list(args.list_path)
    else:
        result = vault_undo(
            path=args.restore_path,
            version=args.version,
            force=args.force,
            dry_run=args.dry_run,
            agent=args.agent,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_undo"))
