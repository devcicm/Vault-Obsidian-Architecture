#!/usr/bin/env python3
"""
Vault History Compact Tool — Rotate .history/ versions per note.

Keeps the N most recent versions per note in .history/, deleting the rest.
Default N=10 as documented in the standard changelog (v39).

Usage:
    python vault_history_compact.py              # interactive: shows what would be deleted
    python vault_history_compact.py --apply     # actually delete old versions
    python vault_history_compact.py --apply --keep 5
    python vault_history_compact.py --note "01_Projects/ans/status.md"
    python vault_history_compact.py --apply --note "01_Projects/ans/status.md"
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from vault_errors import emit_error, wrap_main
from vault_io import get_vault_root
from vault_lib import HISTORY_DIR, utcnow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


DEFAULT_KEEP = 10


def _raiz() -> Path:
    return get_vault_root()


def _history_dir() -> Path:
    return _raiz() / HISTORY_DIR


def _note_stem_from_history_filename(filename: str) -> str:
    """Extract note stem from a .history/ filename.

    Format: {folder__note_stem}-{timestamp}.md
    The stem is the part between the last '__' before the timestamp and the first '-'.
    But timestamps have T and - separators, so we need to parse carefully.

    Actually the format is: folder__stem-YYYY-MM-DDTHH-MM-SS.md
    The timestamp starts with a date, so we find the last occurrence of
    the pattern -YYYY (date prefix).
    """
    without_ext = filename[:-3]
    match = without_ext.rfind("-20")
    if match > 0:
        return without_ext[:match]
    return without_ext


def _parse_history_filename(filename: str) -> Dict[str, Any]:
    """Parse metadata from a .history/ filename."""
    without_ext = filename[:-3]
    match = re.search(r"-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})$", without_ext)
    if match:
        timestamp_str = match.group(1)
        stem = without_ext[:match.start()]
        try:
            ts = datetime.strptime(timestamp_str, "%Y-%m-%dT%H-%M-%S").replace(tzinfo=timezone.utc)
        except ValueError:
            ts = None
        return {"stem": stem, "timestamp": ts, "timestamp_str": timestamp_str}
    return {"stem": without_ext, "timestamp": None, "timestamp_str": ""}


def get_notes_with_history() -> Dict[str, List[Dict[str, Any]]]:
    """Group all history files by their note stem (folder__stem)."""
    history_dir = _history_dir()
    if not history_dir.exists():
        return {}

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for f in history_dir.iterdir():
        if not f.is_file() or not f.name.endswith(".md"):
            continue
        meta = _parse_history_filename(f.name)
        key = meta["stem"]
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "filename": f.name,
            "timestamp": meta["timestamp"],
            "size_bytes": f.stat().st_size,
        })

    for versions in grouped.values():
        versions.sort(key=lambda x: (x["timestamp"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

    return grouped


def vault_history_compact(
    keep: int = DEFAULT_KEEP,
    note_path: str = None,
    apply: bool = False,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Analyze and optionally prune .history/ versions per note.

    Args:
        keep: number of versions to keep per note (default: 10)
        note_path: if provided, only process this specific note
        apply: if True, actually delete the old versions
        dry_run: if True (default), only report without deleting
    """
    grouped = get_notes_with_history()
    if not grouped:
        return {
            "ok": True,
            "action": "none",
            "message": "No history files found in .history/",
            "total_notes": 0,
            "total_versions": 0,
            "versions_deleted": 0,
            "space_freed_bytes": 0,
        }

    if note_path:
        note_path_obj = _raiz() / note_path
        folder = str(note_path_obj.parent.relative_to(_raiz())).replace("\\", "/")
        stem = note_path_obj.stem
        key = f"{folder.replace('/', '__')}__{stem}"
        if key not in grouped:
            return emit_error(
                "vault_history_compact", "HISTORY_NOT_FOUND",
                f"No se encontraron versiones en .history/ para: {note_path}",
            )
        grouped = {key: grouped[key]}

    total_deleted = 0
    space_freed = 0
    deleted_files: List[Dict[str, Any]] = []
    notes_processed = 0

    for key, versions in grouped.items():
        if len(versions) <= keep:
            continue

        notes_processed += 1
        to_delete = versions[keep:]
        for v in to_delete:
            if apply:
                history_file = _history_dir() / v["filename"]
                try:
                    history_file.unlink()
                    total_deleted += 1
                    space_freed += v["size_bytes"]
                    deleted_files.append({
                        "filename": v["filename"],
                        "note_key": key,
                        "size_bytes": v["size_bytes"],
                    })
                except OSError:
                    pass
            else:
                total_deleted += 1
                space_freed += v["size_bytes"]
                deleted_files.append({
                    "filename": v["filename"],
                    "note_key": key,
                    "size_bytes": v["size_bytes"],
                })

    action = "applied" if apply else "dry_run"
    return {
        "ok": True,
        "action": action,
        "keep": keep,
        "total_notes_with_history": len(grouped),
        "notes_above_threshold": notes_processed,
        "total_versions_deleted": total_deleted,
        "space_freed_bytes": space_freed,
        "deleted_files": deleted_files[:50],
        "dry_run": not apply,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault History Compact — rotate .history/ versions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Ver que se borraria (dry-run, default)
  python vault_history_compact.py

  # Aplicar el pruning (borrar versiones antiguas)
  python vault_history_compact.py --apply

  # Mantener solo 5 versiones por nota
  python vault_history_compact.py --apply --keep 5

  # Solo compactar una nota especifica
  python vault_history_compact.py --apply --note "01_Projects/ans/status.md"

Notas:
  - Default: mantiene 10 versiones por nota (N=10, como documenta v39 changelog)
  - --apply es requerido para que algo sea borrado de verdad
  - Los archivos se borran directamente (no van a .trash/)
  - El analisis es por stem de nota: todas las versiones de la misma nota
    (mismo path original) se agrupan juntas
""",
    )
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"Numero de versiones a mantener por nota (default: {DEFAULT_KEEP})")
    parser.add_argument("--note", dest="note_path",
                        help="Solo procesar esta nota especifica")
    parser.add_argument("--apply", action="store_true",
                        help="Aplicar el pruning (sin esto solo hace dry-run)")

    args = parser.parse_args()

    result = vault_history_compact(
        keep=args.keep,
        note_path=args.note_path,
        apply=args.apply,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_history_compact"))
