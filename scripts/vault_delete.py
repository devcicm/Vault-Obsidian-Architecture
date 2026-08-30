#!/usr/bin/env python3
"""
Vault Delete Tool — Delete a note with SP-01 enforcement.

SP-01 exige que antes de eliminar cualquier nota se registre en change-log.
Esta tool lo hace automatico: si no hay entrada de deleted para esta nota,
la crea ANTES de borrar (SP-01), y luego elimina.

Usage:
    python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Duplicate of glossary/jwt.md"
    python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Outdated" --dry-run
    python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Outdated" --trash-only
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from vault_errors import emit_error, wrap_main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    return RepositorioAutoria(construir(root))


def _trash_dir() -> Path:
    trash = _raiz() / "20_Quarantine"
    trash.mkdir(parents=True, exist_ok=True)
    return trash


def _already_deleted(path: str) -> bool:
    """Check if a change_log entry with action=deleted already exists for this path."""
    from vault_change_log import vault_change_log_query

    result = vault_change_log_query(action_filter="deleted")
    if not result.get("ok"):
        return False
    entries = result.get("entries", [])
    path_normalized = path.replace("\\", "/")
    return any(
        e.get("path", "").replace("\\", "/") == path_normalized
        for e in entries
    )


def _write_deleted_entry(path: str, reason: str, agent: str) -> str:
    """Write SP-01 change_log entry via vault_change_log_add. Returns entry id."""
    from vault_change_log import vault_change_log_add

    result = vault_change_log_add(
        action="deleted",
        path=path,
        reason=reason,
        agent=agent,
    )
    if not result.get("ok"):
        raise RuntimeError(f"vault_change_log_add failed: {result}")
    return result["id"]


def vault_delete(
    path: str,
    reason: str,
    agent: str = "claude",
    trash_only: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Delete a note with SP-01 enforcement.

    SP-01 (Delete protocol): antes de eliminar, debe existir una entrada en
    change-log con action=deleted. Esta tool lo garantiza de forma automatica:
    si no existe la entrada, la crea ANTES de borrar.

    Args:
        path: vault-relative note path
        reason: motivo de eliminacion (requerido)
        agent: agente que realiza la eliminacion
        trash_only: solo mover a 20_Quarantine/ en vez de eliminar
        dry_run: no escribir nada, solo reportar
        force: omitir la verificacion SP-01 (para uso interno)
    """
    if not reason or not reason.strip():
        return emit_error(
            "vault_delete", "MISSING_REQUIRED_ARG",
            "`--reason` es obligatorio y no puede estar vacio",
        )

    vault_root = _raiz()
    note_path = vault_root / path

    if not note_path.exists():
        return emit_error(
            "vault_delete", "NOTE_NOT_FOUND",
            f"No existe la nota: {path}",
        )

    if note_path.is_dir():
        return emit_error(
            "vault_delete", "INVALID_PATH",
            f" path '{path}' es una carpeta, no un archivo.",
        )

    already_logged = _already_deleted(path)

    if dry_run:
        if already_logged:
            sp01_note = "SP-01: entrada de change-log ya existente"
        elif force:
            sp01_note = "SP-01: forzado con --force (sin change-log)"
        else:
            sp01_note = "SP-01: WOULD escribir entrada en change-log antes de eliminar"
        return {
            "ok": True,
            "action": "dry_run",
            "note": path,
            "sp01_status": sp01_note,
            "would_delete": not trash_only,
            "would_move_to_quarantine": trash_only,
        }

    if not already_logged and not force:
        entry_id = _write_deleted_entry(path, reason, agent)
        sp01_note = (
            "SP-01: entrada de change-log escrita antes de eliminar "
            f"(id: {entry_id[:8]}...)"
        )
    elif already_logged:
        sp01_note = "SP-01: entrada de change-log ya existente para esta nota"
    else:
        sp01_note = "SP-01: forzado con --force (sin change-log)"

    if trash_only:
        trash_dest = _trash_dir() / note_path.name
        counter = 1
        while trash_dest.exists():
            stem = note_path.stem
            trash_dest = _trash_dir() / f"{stem}_{counter}.md"
            counter += 1
        shutil.move(str(note_path), str(trash_dest))
        return {
            "ok": True,
            "action": "moved_to_quarantine",
            "note": path,
            "quarantined_to": str(trash_dest.relative_to(vault_root)).replace("\\", "/"),
            "sp01_status": sp01_note,
        }
    else:
        note_path.unlink()
        return {
            "ok": True,
            "action": "deleted",
            "note": path,
            "sp01_status": sp01_note,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Delete — delete a note with SP-01 enforcement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SP-01 (Delete Protocol): antes de eliminar, debe existir una entrada en
change-log con action=deleted. Esta tool lo garantiza automaticamente.

Si no existe la entrada para esta nota, la CREA ANTES de borrar.

Ejemplos:
  # Eliminacion normal (crea change-log si no existe, luego borra)
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Duplicate of glossary/jwt.md"

  # Solo mover a cuarentena (no elimina)
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Needs review" --trash-only

  # Simular sin escribir nada
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Test" --dry-run

  # Forzar eliminacion sin change-log (uso interno)
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Test" --force

Notas:
  - --reason es OBLIGATORIO
  - Si la nota ya fue registrada como deleted en change-log, no escribira entrada duplicada
  - --trash-only mueve a 20_Quarantine/ en vez de eliminar
  - --force omite la creacion de change-log (para recovery de la propia tool)
""",
    )
    parser.add_argument("--path", required=True, help="Ruta relativa al vault de la nota a eliminar")
    parser.add_argument("--reason", required=True, help="Motivo de eliminacion (SP-01)")
    parser.add_argument("--agent", default="claude", help="Nombre del agente (default: claude)")
    parser.add_argument("--trash-only", action="store_true",
                        help="Solo mover a 20_Quarantine/ en vez de eliminar")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simular sin escribir nada")
    parser.add_argument("--force", action="store_true",
                        help="Omitir creacion de change-log (uso interno)")

    args = parser.parse_args()
    result = vault_delete(
        path=args.path,
        reason=args.reason,
        agent=args.agent,
        trash_only=args.trash_only,
        dry_run=args.dry_run,
        force=args.force,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_delete"))
