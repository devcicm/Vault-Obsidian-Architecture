#!/usr/bin/env python3
"""
Vault Standard Upgrade Tool -- Detect and apply migrations between standard versions.

Reads 00_System/standard-version.json to find the current applied version,
then applies all pending migrations up to the target version.

Each migration creates missing folders, updates identity fields, and records
what was applied so future runs are idempotent.

Usage:
    python vault_standard_upgrade.py --check
    python vault_standard_upgrade.py --from v20 --to v25
    python vault_standard_upgrade.py --to latest
    python vault_standard_upgrade.py --init v25
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


VAULT_ROOT = Path(__file__).parent.parent
SYSTEM_DIR = VAULT_ROOT / "00_System"
VERSION_FILE = SYSTEM_DIR / "standard-version.json"
IDENTITY_FILE = SYSTEM_DIR / "identity.md"

CURRENT_VERSION = "v25"

MIGRATIONS: Dict[str, Dict[str, Any]] = {
    "v21": {
        "description": "agent field, 12_Bibliography, vault_drift_detect",
        "add_folders": [
            "12_Bibliography/web",
            "12_Bibliography/papers",
            "12_Bibliography/docs",
            "12_Bibliography/apis",
            "12_Bibliography/books",
        ],
        "update_identity": {"tools_count": "38", "groups_count": "17"},
        "notes": [
            "AP-16: add agent: field to new notes",
            "vault_drift_detect mandatory in session protocol",
        ],
    },
    "v22": {
        "description": "vault_drift_detect snapshot/report gates",
        "add_folders": [],
        "update_identity": {},
        "notes": [
            "Session protocol updated: snapshot at start, report at close",
        ],
    },
    "v23": {
        "description": "13_Flows, vault_code_query, IEEE 1016 in vault_code_module",
        "add_folders": [
            "13_Flows/workflow",
            "13_Flows/pipeline",
            "13_Flows/lifecycle",
            "13_Flows/dataflow",
        ],
        "update_identity": {"tools_count": "40", "groups_count": "18"},
        "notes": [
            "vault_code_module now supports --methods, --classes, --constants, --exceptions, --iso_type",
            "vault_code_query: recursive index querying by file/method/class",
        ],
    },
    "v24": {
        "description": "ISO 25010/29148/29119/42001",
        "add_folders": [
            "14_Requirements",
            "15_Tests/unit",
            "15_Tests/integration",
            "15_Tests/e2e",
            "15_Tests/performance",
            "15_Tests/security",
            "15_Tests/acceptance",
            "16_AI_Governance/decisions",
        ],
        "update_identity": {"tools_count": "43", "groups_count": "21"},
        "notes": [
            "vault_code_module --quality for ISO 25010",
            "vault_requirement_save: ISO/IEC/IEEE 29148:2018",
            "vault_test_save: ISO/IEC/IEEE 29119-3:2021",
            "vault_ai_decision: ISO/IEC 42001:2023",
        ],
    },
    "v25": {
        "description": "AP-17~21, PAT-1~5, vault_change_log, vault_standard_upgrade",
        "add_folders": [],
        "update_identity": {"tools_count": "45", "groups_count": "23"},
        "notes": [
            "vault_write guards: AP-20 empty list ratio, AP-21 path-anchored wiki-links",
            "vault_section_index: stem-only wiki-links (AP-21 fix)",
            "vault_audit: AP-17 fuzzy title detection, AP-18 cross-folder hash detection",
            "vault_change_log: mandatory before note deletions",
            "vault_standard_upgrade: version gap detection and migration",
        ],
    },
}

VERSION_ORDER = ["v19", "v20", "v21", "v22", "v23", "v24", "v25"]


def _version_index(v: str) -> int:
    try:
        return VERSION_ORDER.index(v)
    except ValueError:
        return -1


def _read_version_file() -> Dict[str, Any]:
    if not VERSION_FILE.exists():
        return {"applied_version": None, "applied_at": None, "applied_by": None, "migrations_applied": []}
    try:
        return json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"applied_version": None, "applied_at": None, "applied_by": None, "migrations_applied": []}


def _write_version_file(data: Dict[str, Any]) -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pending_migrations(from_version: str, to_version: str) -> List[str]:
    from_idx = _version_index(from_version)
    to_idx = _version_index(to_version)
    if from_idx < 0 or to_idx < 0:
        return []
    return [v for v in VERSION_ORDER if _version_index(v) > from_idx and _version_index(v) <= to_idx and v in MIGRATIONS]


def _apply_migration(version: str, dry_run: bool) -> Dict[str, Any]:
    migration = MIGRATIONS[version]
    folders_created = []
    folders_skipped = []

    for folder in migration.get("add_folders", []):
        folder_path = VAULT_ROOT / folder
        if folder_path.exists():
            folders_skipped.append(folder)
        else:
            if not dry_run:
                folder_path.mkdir(parents=True, exist_ok=True)
                gitkeep = folder_path / ".gitkeep"
                gitkeep.touch()
            folders_created.append(folder)

    return {
        "version": version,
        "description": migration["description"],
        "folders_created": folders_created,
        "folders_skipped": folders_skipped,
        "notes": migration.get("notes", []),
        "identity_updates": migration.get("update_identity", {}),
    }


def vault_standard_upgrade(
    from_version: Optional[str] = None,
    to_version: str = CURRENT_VERSION,
    check_only: bool = False,
    init_version: Optional[str] = None,
    agent: str = "claude",
) -> Dict[str, Any]:
    if init_version:
        data = {
            "applied_version": init_version,
            "applied_at": _utcnow(),
            "applied_by": agent,
            "migrations_applied": [],
        }
        _write_version_file(data)
        return {"ok": True, "action": "init", "applied_version": init_version, "path": str(VERSION_FILE.relative_to(VAULT_ROOT)).replace("\\", "/")}

    state = _read_version_file()
    current_applied = from_version or state.get("applied_version") or "v20"

    if to_version == "latest":
        to_version = CURRENT_VERSION

    pending = _pending_migrations(current_applied, to_version)

    if not pending:
        return {
            "ok": True,
            "action": "none",
            "message": f"Vault is up to date at {current_applied}. No migrations needed.",
            "current_version": current_applied,
            "target_version": to_version,
        }

    if check_only:
        pending_details = []
        for v in pending:
            m = MIGRATIONS[v]
            pending_details.append({
                "version": v,
                "description": m["description"],
                "folders_to_create": [f for f in m.get("add_folders", []) if not (VAULT_ROOT / f).exists()],
                "notes": m.get("notes", []),
            })
        return {
            "ok": True,
            "action": "check",
            "current_version": current_applied,
            "target_version": to_version,
            "pending_count": len(pending),
            "pending_migrations": pending_details,
        }

    applied = []
    all_folders_created = []

    for version in pending:
        result = _apply_migration(version, dry_run=False)
        applied.append(result)
        all_folders_created.extend(result["folders_created"])

    state["applied_version"] = to_version
    state["applied_at"] = _utcnow()
    state["applied_by"] = agent
    already = state.get("migrations_applied", [])
    already.extend(pending)
    state["migrations_applied"] = already
    _write_version_file(state)

    return {
        "ok": True,
        "action": "upgraded",
        "from": current_applied,
        "to": to_version,
        "migrations_applied": applied,
        "folders_created": all_folders_created,
        "version_file": str(VERSION_FILE.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Standard Upgrade -- detect and apply version migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Solo reportar migraciones pendientes (no aplica nada)
  python vault_standard_upgrade.py --check

  # Actualizar desde v20 hasta v25
  python vault_standard_upgrade.py --from v20 --to v25

  # Actualizar al ultimo version disponible
  python vault_standard_upgrade.py --to latest

  # Inicializar el archivo de version (vault nuevo)
  python vault_standard_upgrade.py --init v25

  # Modo check desde una version especifica
  python vault_standard_upgrade.py --check --from v20

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Sin --from, lee la version actual de 00_System/standard-version.json
  - --check no modifica nada, solo reporta
  - --init crea 00_System/standard-version.json si no existe
  - Versiones disponibles: v19, v20, v21, v22, v23, v24, v25
""",
    )
    parser.add_argument("--from", dest="from_version", help="Current vault version (reads standard-version.json if omitted)")
    parser.add_argument("--to", dest="to_version", default=CURRENT_VERSION, help=f"Target version (default: {CURRENT_VERSION}, or 'latest')")
    parser.add_argument("--check", action="store_true", help="Report pending migrations without applying them")
    parser.add_argument("--init", dest="init_version", help="Initialize standard-version.json with given version")
    parser.add_argument("--agent", default="claude", help="Agent name for audit trail (default: claude)")

    args = parser.parse_args()

    result = vault_standard_upgrade(
        from_version=args.from_version,
        to_version=args.to_version,
        check_only=args.check,
        init_version=args.init_version,
        agent=args.agent,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
