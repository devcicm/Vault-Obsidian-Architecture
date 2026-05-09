#!/usr/bin/env python3
"""
vault_manifest.py — Genera manifiesto de tools con estado (active/deprecated/internal).

Escribe 00_System/tools-manifest.json con el estado de cada tool:
  {name, status, group, replaced_by?, deprecated_since?}

Las tools deprecadas emiten _deprecation en su output JSON (campo adicional, no rompe nada).
Las tools internas (vault_index, vault_dataset) están disponibles pero no expuestas al agente.

Usage:
    python vault_manifest.py                # genera/actualiza tools-manifest.json
    python vault_manifest.py --check        # muestra manifiesto sin escribir
    python vault_manifest.py --status active     # filtra por estado
    python vault_manifest.py --status deprecated # lista tools deprecadas
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).parent
VAULT_ROOT = SCRIPTS_DIR.parent
SYSTEM_DIR = VAULT_ROOT / "00_System"
MANIFEST_FILE = SYSTEM_DIR / "tools-manifest.json"

# ──────────────────────────────────────────────────────────────────────────────
# Tool status registry
# ──────────────────────────────────────────────────────────────────────────────

DEPRECATED_TOOLS: Dict[str, Dict[str, str]] = {
    "vault_migrate":    {"replaced_by": "vault_migrate_docs",    "since": "v25", "reason": "vault_migrate_docs is the canonical migration tool with full project support"},
    "vault_reorganize": {"replaced_by": "vault_migrate_docs",    "since": "v25", "reason": "Dynamic dest detection is handled by vault_migrate_docs"},
    "vault_tools":      {"replaced_by": "See individual tools",  "since": "v22", "reason": "Monolithic script superseded by dedicated tools per group"},
    "vault_create":     {"replaced_by": "vault_write",           "since": "v21", "reason": "vault_write handles all note creation with AP guards"},
    "vault_render":     {"replaced_by": "vault_diagram_save",    "since": "v22", "reason": "vault_diagram_save generates Mermaid diagrams with ERD support"},
}

INTERNAL_TOOLS: List[str] = ["vault_dataset", "vault_index"]

# Tools not exposed to agent (test/build tooling)
META_TOOLS: List[str] = ["vault_test_runner", "vault_compact_contracts", "vault_manifest"]

# Group lookup (same as in vault_compact_contracts)
TOOL_GROUPS: Dict[str, str] = {
    "vault_write": "Core", "vault_read": "Core", "vault_search": "Core",
    "vault_list": "Core", "vault_append": "Core", "vault_diff": "Core", "vault_merge": "Core",
    "vault_log_error": "Observabilidad",
    "vault_pattern_save": "Patrones", "vault_pattern_list": "Patrones",
    "vault_diagram_save": "Diagramas", "vault_relation_add": "Diagramas",
    "vault_knowledge_save": "Conocimiento", "vault_knowledge_get": "Conocimiento",
    "vault_audit": "Salud", "vault_validate": "Salud", "vault_graph": "Salud",
    "vault_runbook_save": "Runbooks", "vault_runbook_log": "Runbooks",
    "vault_infra_save": "Infraestructura", "vault_infra_map": "Infraestructura", "vault_env_save": "Infraestructura",
    "vault_migrate_docs": "Migración", "vault_migrate_rollback": "Migración",
    "vault_timeline": "Línea de tiempo",
    "vault_project_status": "Vista proyecto", "vault_project_overview": "Vista proyecto",
    "vault_code_module": "Código", "vault_code_relation": "Código",
    "vault_code_map": "Código", "vault_code_query": "Código",
    "vault_backup": "Backups", "vault_backup_list": "Backups", "vault_restore": "Backups",
    "vault_security_scan": "Seguridad",
    "vault_section_index": "Índices", "vault_master_index": "Índices", "vault_reindex": "Índices",
    "vault_bibliography_save": "Bibliografía",
    "vault_drift_detect": "Drift",
    "vault_flow_save": "Flujos",
    "vault_requirement_save": "Requerimientos",
    "vault_test_save": "Tests",
    "vault_ai_decision": "IA Governance",
    "vault_standard_upgrade": "Versionado",
    "vault_change_log": "Change Log",
    # Legacy
    "vault_migrate": "Migración (legacy)", "vault_reorganize": "Migración (legacy)",
    "vault_tools": "misc (legacy)", "vault_create": "Core (legacy)", "vault_render": "Diagramas (legacy)",
    # Internal
    "vault_dataset": "internal", "vault_index": "internal",
    # Meta
    "vault_test_runner": "meta", "vault_compact_contracts": "meta", "vault_manifest": "meta",
}


def _build_manifest() -> List[Dict[str, Any]]:
    scripts = sorted(p.stem for p in SCRIPTS_DIR.glob("vault_*.py") if p.stem != "vault_errors")
    manifest = []

    for name in scripts:
        if name in DEPRECATED_TOOLS:
            dep = DEPRECATED_TOOLS[name]
            entry: Dict[str, Any] = {
                "name": name,
                "status": "deprecated",
                "group": TOOL_GROUPS.get(name, "misc"),
                "replaced_by": dep["replaced_by"],
                "deprecated_since": dep["since"],
                "reason": dep["reason"],
            }
        elif name in INTERNAL_TOOLS:
            entry = {
                "name": name,
                "status": "internal",
                "group": "internal",
                "note": "Not exposed to agent; used internally by other tools",
            }
        elif name in META_TOOLS:
            entry = {
                "name": name,
                "status": "meta",
                "group": "meta",
                "note": "Test/build tooling; not part of the 53-tool surface",
            }
        else:
            entry = {
                "name": name,
                "status": "active",
                "group": TOOL_GROUPS.get(name, "misc"),
            }
        manifest.append(entry)

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_manifest -- genera manifiesto de estado de las vault tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_manifest.py                     # genera 00_System/tools-manifest.json
  python vault_manifest.py --check             # muestra sin escribir
  python vault_manifest.py --status deprecated # lista solo tools deprecadas
  python vault_manifest.py --status active     # lista solo tools activas
""",
    )
    parser.add_argument("--check", action="store_true", help="Mostrar manifiesto sin escribir archivo")
    parser.add_argument("--status", choices=["active", "deprecated", "internal", "meta"], help="Filtrar por estado")

    args = parser.parse_args()

    manifest = _build_manifest()

    if args.status:
        manifest = [e for e in manifest if e["status"] == args.status]

    result: Dict[str, Any] = {
        "ok": True,
        "total": len(manifest),
        "active": sum(1 for e in manifest if e["status"] == "active"),
        "deprecated": sum(1 for e in manifest if e["status"] == "deprecated"),
        "internal": sum(1 for e in manifest if e["status"] == "internal"),
        "meta": sum(1 for e in manifest if e["status"] == "meta"),
        "tools": manifest,
    }

    if args.check:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "total": result["total"],
        "active": result["active"],
        "deprecated": result["deprecated"],
        "path": str(MANIFEST_FILE.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
