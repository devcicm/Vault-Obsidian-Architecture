#!/usr/bin/env python3
"""
Vault Restore Tool — Restore vault from backup

Restores the vault from a backup snapshot. Destructive operation.
Requires confirm=true to proceed. Automatically rebuilds search index.

Usage:
    python vault_restore.py --backup_name "vault-2026-05-06-143022-antes-de-migracion" --confirm true
"""

import argparse
import json
import shutil
import sys
from vault_errors import wrap_main
from pathlib import Path
from typing import Any, Dict

from vault_io import VAULT_ROOT
BACKUP_ROOT = Path(__file__).parent.parent.parent / "vault-backups"
INDEX_FILE = VAULT_ROOT / "99_Index" / "search-index.json"


def vault_restore(backup_name: str, confirm: bool = False) -> Dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "error": "confirm must be true to proceed. This is a destructive operation.",
            "hint": "Run vault_backup(label) first to backup current state, then confirm with confirm:true",
        }

    backup_path = BACKUP_ROOT / backup_name
    if not backup_path.exists():
        return {
            "ok": False,
            "error": f"Backup not found: {backup_name}",
        }

    manifest_path = backup_path / ".manifest.json"
    note_count = 0
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        note_count = manifest.get("vault", {}).get("totals", {}).get("notes", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    for item in VAULT_ROOT.iterdir():
        if item.name.startswith("."):
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    for item in backup_path.iterdir():
        if item.name.startswith("."):
            continue
        dest = VAULT_ROOT / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    try:
        import subprocess

        index_script = VAULT_ROOT.parent / "data" / "vault" / "scripts" / "vault_index.py"
        if index_script.exists():
            subprocess.run([sys.executable, str(index_script)], capture_output=True, timeout=60)
    except Exception:
        pass

    return {
        "ok": True,
        "restored_from": backup_name,
        "noteCount": note_count,
        "message": f"Vault restored from {backup_name} ({note_count} notes)",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Restore Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_restore.py --backup_name "vault-2026-05-06-143022-antes-de-migracion" --confirm true
  python vault_restore.py --backup_name "vault-2026-05-01-120000" --confirm false

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Operacion DESTRUCTIVA -- reemplaza todo el contenido del vault
  - Ejecutar vault_backup.py primero para preservar estado actual
  - --confirm false (default) solo muestra info sin restaurar
""",
    )
    parser.add_argument("--backup_name", required=True, help="Exact backup name")
    parser.add_argument("--confirm", type=lambda x: x.lower() == "true", default=False, help="Must be true")

    args = parser.parse_args()
    result = vault_restore(args.backup_name, args.confirm)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_restore"))
