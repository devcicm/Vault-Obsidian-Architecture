#!/usr/bin/env python3
"""
Vault Backup Tool — Full vault snapshot with manifest

Creates a complete snapshot of the vault with detailed manifest per section.
Stores backup in vault-backups/ directory with .manifest.json and updates registry.

Usage:
    python vault_backup.py
    python vault_backup.py --label "antes-de-migracion"
"""

import argparse
import json
import re
import shutil
import sys
from vault_errors import wrap_main
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

VAULT_ROOT = Path(__file__).parent.parent
BACKUP_ROOT = Path(__file__).parent.parent.parent / "vault-backups"
INDEX_FILE = VAULT_ROOT / "99_Index" / "search-index.json"
REGISTRY_FILE = BACKUP_ROOT / ".backup-registry.json"


def count_items(folder: Path) -> tuple[int, int, int]:
    notes = 0
    files = 0
    size = 0

    for item in folder.rglob("*"):
        if item.is_file():
            files += 1
            if item.suffix == ".md":
                notes += 1
            try:
                size += item.stat().st_size
            except OSError:
                pass

    return notes, files, size


def scan_backup(backup_path: Path) -> Dict[str, Any]:
    sections = []
    total_notes = 0
    total_files = 0
    total_size = 0

    vault_folder = backup_path

    for item in sorted(vault_folder.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            notes, files, size = count_items(item)
            if notes > 0 or files > 0:
                sections.append(
                    {
                        "folder": item.name,
                        "notes": notes,
                        "files": files,
                        "sizeKB": round(size / 1024, 1),
                    }
                )
            total_notes += notes
            total_files += files
            total_size += size

    for item in vault_folder.iterdir():
        if item.is_file() and item.suffix not in [".json"]:
            try:
                total_files += 1
                total_size += item.stat().st_size
            except OSError:
                pass

    return {
        "sections": sections,
        "totals": {
            "notes": total_notes,
            "files": total_files,
            "sizeKB": round(total_size / 1024, 1),
        },
    }


def load_registry() -> Dict[str, Any]:
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"backups": []}


def save_registry(registry: Dict[str, Any]) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def vault_backup(label: Optional[str] = None) -> Dict[str, Any]:
    if label:
        label_slug = re.sub(r"[^\w\s-]", "", label.lower())
        label_slug = re.sub(r"[\s_]+", "-", label_slug)
        label_slug = re.sub(r"^-+|-+$", "", label_slug)
    else:
        label_slug = ""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    backup_name = f"vault-{timestamp}" + (f"-{label_slug}" if label_slug else "")

    backup_path = BACKUP_ROOT / backup_name
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    vault_src = VAULT_ROOT

    for item in vault_src.iterdir():
        if item.name.startswith("."):
            continue
        dest = backup_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    manifest_data = scan_backup(backup_path)
    now = _utcnow()
    manifest = {
        "name": backup_name,
        "label": label_slug or "",
        "createdAt": now,
        "vault": manifest_data,
    }

    manifest_path = backup_path / ".manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    registry = load_registry()
    registry["backups"].insert(
        0,
        {
            "name": backup_name,
            "label": label_slug or "",
            "createdAt": now,
            "noteCount": manifest_data["totals"]["notes"],
            "fileCount": manifest_data["totals"]["files"],
            "sizeKB": manifest_data["totals"]["sizeKB"],
            "sections": [s["folder"] for s in manifest_data["sections"]],
        },
    )
    save_registry(registry)

    return {
        "ok": True,
        "name": backup_name,
        "path": str(backup_path.relative_to(Path(__file__).parent.parent.parent)).replace("\\", "/") + "/",
        "manifest": manifest_data,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Backup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_backup.py
  python vault_backup.py --label "antes-de-migracion"
  python vault_backup.py --label "sprint-3-checkpoint"
  python vault_backup.py --label "antes-de-refactor"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Crea snapshot completo en vault-backups/ con .manifest.json
  - Registra el backup en .backup-registry.json para vault_backup_list.py
""",
    )
    parser.add_argument("--label", help="Optional label (e.g., 'antes-de-migracion')")

    args = parser.parse_args()
    result = vault_backup(args.label)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_backup"))
