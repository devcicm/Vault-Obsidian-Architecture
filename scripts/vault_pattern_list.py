#!/usr/bin/env python3
"""
Vault Pattern List Tool — List patterns by project and status

Lists all registered patterns grouped by state (implementado, en_progreso, planificado, deprecado).
Without filters: shows all patterns. With filters: shows only matching ones.

Usage:
    python vault_pattern_list.py
    python vault_pattern_list.py --project "mi-api"
    python vault_pattern_list.py --type "code"
    python vault_pattern_list.py --status "implementado"
"""

import argparse
import json
import sys
from vault_errors import wrap_main
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_io import VAULT_ROOT
PATTERNS_DIR = VAULT_ROOT / "05_Patterns"
INDEX_FILE = PATTERNS_DIR / "index.json"


def vault_pattern_list(
    project: Optional[str] = None,
    pattern_type: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"ok": False, "error": "Pattern index not found. Save patterns first with vault_pattern_save."}

    patterns = index.get("patterns", [])

    if project:
        patterns = [p for p in patterns if p.get("project", "").lower() == project.lower()]
    if pattern_type:
        patterns = [p for p in patterns if p.get("type", "").lower() == pattern_type.lower()]
    if status:
        status_normalized = status.lower().replace(" ", "_")
        patterns = [p for p in patterns if p.get("status", "").lower() == status_normalized]

    grouped: Dict[str, List[str]] = {
        "implementado": [],
        "en_progreso": [],
        "planificado": [],
        "deprecado": [],
        "refactoring": [],
    }

    for p in patterns:
        s = p.get("status", "")
        if s in grouped:
            grouped[s].append(p.get("pattern", ""))
        else:
            grouped["implementado"].append(p.get("pattern", ""))

    return {
        "ok": True,
        "total": len(patterns),
        "grouped": grouped,
        "patterns": patterns,
        "filters": {
            "project": project,
            "type": pattern_type,
            "status": status,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Pattern List Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_pattern_list.py
  python vault_pattern_list.py --project "mi-api"
  python vault_pattern_list.py --type "code"
  python vault_pattern_list.py --status "implementado"
  python vault_pattern_list.py --project "ans" --status "en_progreso"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Requiere que vault_pattern_save haya sido ejecutado al menos una vez
  - Estados: implementado, en_progreso, planificado, deprecado, refactoring
""",
    )
    parser.add_argument("--project", help="Filter by project")
    parser.add_argument("--type", help="Filter by pattern type (design, architecture, code, integration)")
    parser.add_argument("--status", help="Filter by status")

    args = parser.parse_args()
    result = vault_pattern_list(args.project, args.type, args.status)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_pattern_list"))
