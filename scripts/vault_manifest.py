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

INTERNAL_TOOLS: List[str] = ["vault_dataset", "vault_index", "vault_io", "vault_link_safety"]

# DQ/CIA metadata per tool (v27+). data_fundamentals is DERIVED from
# vault_fundamentals.FUNDAMENTALS registry (single source of truth).
DQ_METADATA: Dict[str, Dict[str, Any]] = {
    # ── Data Quality / Propagation core ─────────────────────────────────────
    "vault_quality_check": {
        "dq_dimensions": ["integrity", "consistency", "completeness", "accuracy",
                          "validity", "timeliness", "authenticity", "non_repudiation", "uniqueness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    "vault_fundamentals": {
        "dq_dimensions": [],
        "cia_scope": ["integrity", "availability", "sensitivity"],
        "propagation_aware": False,
        "is_registry": True,
    },
    "vault_impact": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["integrity"],
        "propagation_aware": True,
    },
    "vault_propagate": {
        "dq_dimensions": ["consistency", "timeliness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    # ── Salud / Observabilidad ───────────────────────────────────────────────
    "vault_audit": {
        "dq_dimensions": ["completeness", "uniqueness", "consistency", "timeliness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    "vault_validate": {
        "dq_dimensions": ["validity", "integrity", "authenticity"],
        "cia_scope": ["integrity", "availability", "sensitivity"],
        "propagation_aware": False,
    },
    "vault_graph": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["availability"],
        "propagation_aware": True,
    },
    "vault_drift_detect": {
        "dq_dimensions": ["timeliness", "accuracy"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_security_scan": {
        "dq_dimensions": ["validity", "integrity"],
        "cia_scope": ["integrity", "sensitivity"],
        "propagation_aware": False,
    },
    # ── Core (write path) ────────────────────────────────────────────────────
    "vault_write": {
        "dq_dimensions": ["integrity", "authenticity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_append": {
        "dq_dimensions": ["integrity", "authenticity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_merge": {
        "dq_dimensions": ["consistency", "uniqueness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    # ── Core (read path) ────────────────────────────────────────────────────
    "vault_read": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_search": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_list": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_diff": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    # ── Índices ──────────────────────────────────────────────────────────────
    "vault_reindex": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_section_index": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["availability"],
        "propagation_aware": True,
    },
    "vault_master_index": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["availability"],
        "propagation_aware": True,
    },
    # ── Change Log / Auditoría ───────────────────────────────────────────────
    "vault_change_log": {
        "dq_dimensions": ["non_repudiation"],
        "cia_scope": ["integrity"],
        "propagation_aware": True,
    },
    "vault_log_error": {
        "dq_dimensions": ["non_repudiation", "integrity"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    # ── Conocimiento / Patrones / Diagramas ──────────────────────────────────
    "vault_knowledge_save": {
        "dq_dimensions": ["integrity", "authenticity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_knowledge_get": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_pattern_save": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_pattern_list": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_diagram_save": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_relation_add": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["integrity"],
        "propagation_aware": True,
    },
    "vault_bibliography_save": {
        "dq_dimensions": ["authenticity"],
        "cia_scope": ["integrity", "authenticity"],
        "propagation_aware": False,
    },
    # ── Infraestructura ──────────────────────────────────────────────────────
    "vault_infra_save": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    "vault_infra_map": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["availability"],
        "propagation_aware": True,
    },
    "vault_env_save": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity", "sensitivity"],
        "propagation_aware": False,
    },
    # ── Runbooks ─────────────────────────────────────────────────────────────
    "vault_runbook_save": {
        "dq_dimensions": ["integrity", "completeness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    "vault_runbook_log": {
        "dq_dimensions": ["non_repudiation"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    # ── Migración ────────────────────────────────────────────────────────────
    "vault_migrate_docs": {
        "dq_dimensions": ["integrity", "completeness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    "vault_migrate_rollback": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": True,
    },
    # ── Backups ──────────────────────────────────────────────────────────────
    "vault_backup": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    "vault_backup_list": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_restore": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    # ── Código ───────────────────────────────────────────────────────────────
    "vault_code_module": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_code_relation": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["integrity"],
        "propagation_aware": True,
    },
    "vault_code_map": {
        "dq_dimensions": ["consistency"],
        "cia_scope": ["availability"],
        "propagation_aware": True,
    },
    "vault_code_query": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    # ── Requerimientos / Tests / Flujos ──────────────────────────────────────
    "vault_requirement_save": {
        "dq_dimensions": ["integrity", "completeness"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_test_save": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_flow_save": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    # ── IA Governance / Versionado / Timeline ────────────────────────────────
    "vault_ai_decision": {
        "dq_dimensions": ["authenticity", "non_repudiation"],
        "cia_scope": ["integrity", "sensitivity"],
        "propagation_aware": False,
    },
    "vault_standard_upgrade": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    "vault_timeline": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_project_status": {
        "dq_dimensions": ["integrity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_project_overview": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    # ── Tokens ───────────────────────────────────────────────────────────────
    "vault_tokens": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_token_counter": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    "vault_token_service": {
        "dq_dimensions": [],
        "cia_scope": ["availability"],
        "propagation_aware": False,
    },
    # ── Meta tools ───────────────────────────────────────────────────────────
    "vault_spec_memory": {
        "dq_dimensions": ["integrity", "consistency", "completeness", "validity",
                          "timeliness", "authenticity", "non_repudiation"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    "vault_test_runner": {
        "dq_dimensions": ["validity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_compact_contracts": {
        "dq_dimensions": ["completeness", "validity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_manifest": {
        "dq_dimensions": ["completeness", "validity", "authenticity"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
}


def _derive_fundamentals_by_tool() -> Dict[str, List[str]]:
    """Single source of truth: derive data_fundamentals per tool from vault_fundamentals registry."""
    try:
        from vault_fundamentals import FUNDAMENTALS as _FUNDS
    except ImportError:
        return {}
    by_tool: Dict[str, List[str]] = {}
    for f in _FUNDS:
        for tool in f.get("tools", []):
            by_tool.setdefault(tool, []).append(f["id"])
    return {k: sorted(v) for k, v in by_tool.items()}


_FUND_BY_TOOL = _derive_fundamentals_by_tool()

# Tools not exposed to agent (test/build tooling)
META_TOOLS: List[str] = ["vault_test_runner", "vault_compact_contracts", "vault_manifest", "vault_spec_memory"]

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
    "vault_tokens": "Tokens", "vault_token_counter": "Tokens", "vault_token_service": "Tokens",
    # v27 Data Quality & Propagation
    "vault_quality_check": "Data Quality",
    "vault_fundamentals": "Data Quality",
    "vault_impact": "Propagación",
    "vault_propagate": "Propagación",
    # Legacy
    "vault_migrate": "Migración (legacy)", "vault_reorganize": "Migración (legacy)",
    "vault_tools": "misc (legacy)", "vault_create": "Core (legacy)", "vault_render": "Diagramas (legacy)",
    # Internal
    "vault_dataset": "internal", "vault_index": "internal",
    # Meta
    "vault_test_runner": "meta", "vault_compact_contracts": "meta", "vault_manifest": "meta",
    "vault_spec_memory": "meta",
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
        # Attach DQ/CIA metadata if available (v27)
        if name in DQ_METADATA:
            entry.update(DQ_METADATA[name])
        # Derive data_fundamentals from vault_fundamentals registry (single source of truth)
        if name in _FUND_BY_TOOL:
            entry["data_fundamentals"] = _FUND_BY_TOOL[name]
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

    # Read standard version from 00_System/standard-version.json if available
    _version = "unknown"
    try:
        _sv = SYSTEM_DIR / "standard-version.json"
        if _sv.exists():
            import json as _j
            _version = _j.loads(_sv.read_text(encoding="utf-8")).get("version", "unknown")
            _version = f"v{_version}" if isinstance(_version, int) else str(_version)
    except Exception:
        pass

    result: Dict[str, Any] = {
        "ok": True,
        "standard_version": _version,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
