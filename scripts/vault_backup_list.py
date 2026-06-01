#!/usr/bin/env python3
"""
Vault Backup List Tool — List all vault backups from registry

Lists all backups from .backup-registry.json or reads .manifest.json files as fallback.

Usage:
    python vault_backup_list.py
"""

import argparse
import json
import sys
from vault_errors import wrap_main
from pathlib import Path
from typing import Any, Dict

from vault_io import VAULT_ROOT
BACKUP_ROOT = Path(__file__).parent.parent.parent / "vault-backups"
REGISTRY_FILE = BACKUP_ROOT / ".backup-registry.json"


def load_registry() -> Dict[str, Any]:
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"backups": []}


def load_manifest_fallback(backup_path: Path) -> Dict[str, Any]:
    manifest_path = backup_path / ".manifest.json"
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def vault_backup_list() -> Dict[str, Any]:
    registry = load_registry()
    backups = registry.get("backups", [])

    if not backups:
        backups = []
        if BACKUP_ROOT.exists():
            for item in sorted(BACKUP_ROOT.iterdir(), reverse=True):
                if item.is_dir() and not item.name.startswith("."):
                    manifest = load_manifest_fallback(item)
                    vault_data = manifest.get("vault", {})
                    backups.append(
                        {
                            "name": item.name,
                            "label": manifest.get("label", ""),
                            "createdAt": manifest.get("createdAt", ""),
                            "noteCount": vault_data.get("totals", {}).get("notes", 0),
                            "fileCount": vault_data.get("totals", {}).get("files", 0),
                            "sizeKB": vault_data.get("totals", {}).get("sizeKB", 0),
                            "sections": [s["folder"] for s in vault_data.get("sections", [])],
                        }
                    )

    return {
        "ok": True,
        "total": len(backups),
        "backups": backups,
        "message": f"{len(backups)} backups found",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Backup List Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_backup_list.py

Notas:
  - Lee .backup-registry.json del directorio vault-backups/
  - Si no hay registry, escanea los directorios de backup directamente
  - Los backups se crean con vault_backup.py
""",
    )
    _ = parser.parse_args()

    result = vault_backup_list()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_backup_list"))
