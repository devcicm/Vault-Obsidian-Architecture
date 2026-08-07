#!/usr/bin/env python3
"""
vault_manifest.py — Genera manifiesto de tools + bootstraps/actualiza tool-spec.json.

Modos:
  normal        Escribe 00_System/tools-manifest.json desde tool-spec.json (spec-driven).
                Si tool-spec.json no existe, usa datos hardcodeados como fallback.
  --bootstrap   Genera <vault>/00_System/tool-spec.json combinando datos hardcodeados +
                introspección. Ejecutar una sola vez (o al agregar datos nuevos al spec).
                Desde v39 el contrato vive DENTRO del vault (AP-36); la ruta se resuelve
                con vault_io.tool_spec_path(), nunca desde __file__.
  --validate    Delega a vault_spec_validate.py — muestra drift entre spec e implementación.
  --check       Muestra el manifiesto sin escribir.

Flujo spec-driven:
  1. python vault_manifest.py --bootstrap     ← genera tool-spec.json inicial
  2. Editar tool-spec.json antes de cada nueva tool
  3. Implementar el script
  4. python vault_manifest.py --validate      ← verificar conformidad
  5. python vault_manifest.py                 ← actualizar tools-manifest.json

Usage:
    python vault_manifest.py                     # genera tools-manifest.json desde spec
    python vault_manifest.py --bootstrap         # (re)genera tool-spec.json
    python vault_manifest.py --validate          # muestra drift spec vs implementación
    python vault_manifest.py --check             # muestra sin escribir
    python vault_manifest.py --status active     # filtra por estado
    python vault_manifest.py --status deprecated # lista tools deprecadas
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

SCRIPTS_DIR = Path(__file__).parent

from vault_io import (  # noqa: E402
    atomic_write_json,
    get_vault_root,
    resolve_tool_spec,
    tool_spec_path,
)
from vault_errors import wrap_main

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
    # ── Normas y Etiquetas de Código (v30) ──────────────────────────────────
    "vault_norms": {
        "dq_dimensions": ["validity", "integrity", "consistency"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    "vault_code_tag": {
        "dq_dimensions": ["integrity", "authenticity"],
        "cia_scope": ["integrity"],
        "propagation_aware": False,
    },
    # ── Producción y SRE (v31) ────────────────────────────────────────────────
    "vault_incident_save": {
        "dq_dimensions": ["integrity", "non_repudiation", "timeliness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    "vault_slo_save": {
        "dq_dimensions": ["validity", "accuracy", "timeliness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": False,
    },
    # ── Release y Entornos (v31) ──────────────────────────────────────────────
    "vault_env_matrix": {
        "dq_dimensions": ["integrity", "consistency"],
        "cia_scope": ["integrity", "availability", "sensitivity"],
        "propagation_aware": False,
    },
    "vault_release_save": {
        "dq_dimensions": ["integrity", "non_repudiation"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
    # ── Riesgos y Calidad (v32) ───────────────────────────────────────────────
    "vault_risk_save": {
        "dq_dimensions": ["validity", "integrity", "accuracy"],
        "cia_scope": ["integrity", "availability", "sensitivity"],
        "propagation_aware": True,
    },
    "vault_privacy_save": {
        "dq_dimensions": ["integrity", "non_repudiation", "compliance"],
        "cia_scope": ["integrity", "sensitivity"],
        "propagation_aware": False,
    },
    "vault_ncr_save": {
        "dq_dimensions": ["integrity", "non_repudiation", "timeliness"],
        "cia_scope": ["integrity", "availability"],
        "propagation_aware": True,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Spec-driven helpers
# ──────────────────────────────────────────────────────────────────────────────


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.meta_toolkit.repositorio import RepositorioMetaToolkit  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioMetaToolkit:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioMetaToolkit(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _manifest_file() -> Path:
    return _repo().manifiesto_tools


def _load_spec() -> Optional[Dict[str, Any]]:
    """Carga tool-spec.json si existe. Retorna None si no existe (fallback a hardcoded)."""
    spec_file = resolve_tool_spec()
    if spec_file is None:
        return None
    try:
        return json.loads(spec_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_manifest_from_spec(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Genera la lista de entradas del manifiesto desde tool-spec.json."""
    manifest = []
    for name, entry in sorted(spec.get("tools", {}).items()):
        m: Dict[str, Any] = {
            "name": name,
            "status": entry.get("status", "active"),
            "group": entry.get("group", "misc"),
        }
        if entry.get("status") == "deprecated":
            m["replaced_by"]      = entry.get("replaced_by", "")
            m["deprecated_since"] = entry.get("deprecated_since", "")
            m["reason"]           = entry.get("deprecation_reason", "")
        if entry.get("status") in ("internal", "meta"):
            m["note"] = "Not exposed to agent"
        dq = entry.get("dq", {})
        if dq:
            m.update(dq)
        funds = entry.get("fundamentals", [])
        if funds:
            m["data_fundamentals"] = funds
        manifest.append(m)
    return manifest


def _extract_required_flags(source: str) -> List[str]:
    """Extrae --flags marcados required=True en argparse."""
    flags: List[str] = []
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "add_argument(" in line:
            call = line
            depth = call.count("(") - call.count(")")
            j = i + 1
            while depth > 0 and j < len(lines):
                call += " " + lines[j].strip()
                depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            names = re.findall(r"""add_argument\(\s*["']([^"']+)["']""", call)
            if names:
                flag = names[0]
                is_required = "required=True" in call or not flag.startswith("-")
                if is_required and flag.startswith("-"):
                    flags.append(flag)
        i += 1
    return flags


def _bootstrap_spec() -> Dict[str, Any]:
    """
    Genera tool-spec.json combinando datos hardcodeados + introspección de scripts.
    Incluye declared_returns desde vault_spec_memory.DECLARED_RETURNS.
    """
    # Import DECLARED_RETURNS (fuente actual de retornos declarados)
    _dr: Dict[str, List[str]] = {}
    try:
        from vault_spec_memory import DECLARED_RETURNS as _DR
        _dr = _DR
    except ImportError:
        pass

    # Import GROUPS desde vault_compact_contracts para group_id
    _group_by_tool: Dict[str, Dict] = {}
    try:
        from vault_compact_contracts import GROUPS as _GROUPS
        for g in _GROUPS:
            for t in g["tools"]:
                _group_by_tool[t] = g
    except ImportError:
        pass

    # Combinar todos los nombres de tools conocidos
    all_names: Set[str] = set(TOOL_GROUPS.keys())
    all_names.update(_group_by_tool.keys())
    # Descubrir scripts activos que puedan no estar en el registry
    for p in SCRIPTS_DIR.glob("vault_*.py"):
        stem = p.stem
        if stem not in ("vault_errors", "vault_io"):
            all_names.add(stem)

    tools: Dict[str, Any] = {}
    for name in sorted(all_names):
        # Estado
        if name in DEPRECATED_TOOLS:
            status = "deprecated"
        elif name in INTERNAL_TOOLS:
            status = "internal"
        elif name in META_TOOLS:
            status = "meta"
        else:
            status = "active"

        # Grupo
        gdata = _group_by_tool.get(name, {})
        group_name = gdata.get("name", TOOL_GROUPS.get(name, "misc"))
        group_id   = gdata.get("id", 0)

        # Args (introspección del script)
        required_args: List[str] = []
        script_path = SCRIPTS_DIR / f"{name}.py"
        if script_path.exists():
            try:
                src = script_path.read_text(encoding="utf-8", errors="replace")
                required_args = _extract_required_flags(src)
            except Exception:
                pass

        entry: Dict[str, Any] = {
            "group":            group_name,
            "group_id":         group_id,
            "status":           status,
            "required_args":    required_args,
            "declared_returns": _dr.get(name, []),
            "dq":               DQ_METADATA.get(name, {
                "dq_dimensions":    [],
                "cia_scope":        [],
                "propagation_aware": False,
            }),
            "fundamentals": _FUND_BY_TOOL.get(name, []),
        }

        if name in DEPRECATED_TOOLS:
            dep = DEPRECATED_TOOLS[name]
            entry["replaced_by"]        = dep["replaced_by"]
            entry["deprecated_since"]   = dep["since"]
            entry["deprecation_reason"] = dep["reason"]

        tools[name] = entry

    return {
        "version":     "v32",
        "schema":      "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Spec-driven tool contracts. "
            "Editar este archivo ANTES de implementar una nueva tool. "
            "Validar con: python vault_spec_validate.py"
        ),
        "tools": tools,
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
    "vault_onboard": "Versionado",
    "vault_change_log": "Change Log",
    "vault_tokens": "Tokens", "vault_token_counter": "Tokens", "vault_token_service": "Tokens",
    # v27 Data Quality & Propagation
    "vault_quality_check": "Data Quality",
    "vault_fundamentals": "Data Quality",
    "vault_impact": "Propagación",
    "vault_propagate": "Propagación",
    # v29 Session Delta y Tags
    "vault_delta": "Session Delta y Tags",
    "vault_tags": "Session Delta y Tags",
    # v30 Normas y Etiquetas de Código
    "vault_norms": "Normas y Etiquetas",
    "vault_code_tag": "Normas y Etiquetas",
    # v31 Producción y SRE
    "vault_incident_save": "Producción y SRE",
    "vault_slo_save": "Producción y SRE",
    # v31 Release y Entornos
    "vault_env_matrix": "Release y Entornos",
    "vault_release_save": "Release y Entornos",
    # v32 Gestión de Riesgos y Calidad
    "vault_risk_save":    "Riesgos y Calidad",
    "vault_privacy_save": "Riesgos y Calidad",
    "vault_ncr_save":     "Riesgos y Calidad",
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


def _read_version() -> str:
    try:
        sv = _system_dir() / "standard-version.json"
        if sv.exists():
            v = json.loads(sv.read_text(encoding="utf-8")).get("version", "unknown")
            return f"v{v}" if isinstance(v, int) else str(v)
    except Exception:
        pass
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_manifest — manifiesto de tools (spec-driven desde tool-spec.json)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_manifest.py --bootstrap         # genera tool-spec.json (primera vez o al actualizar)
  python vault_manifest.py                     # genera 00_System/tools-manifest.json desde spec
  python vault_manifest.py --validate          # muestra drift entre spec e implementación
  python vault_manifest.py --check             # muestra manifiesto sin escribir
  python vault_manifest.py --status deprecated # lista solo tools deprecadas
  python vault_manifest.py --status active     # lista solo tools activas
""",
    )
    parser.add_argument("--bootstrap", action="store_true",
                        help="Genera/actualiza <vault>/00_System/tool-spec.json desde datos hardcodeados + introspección")
    parser.add_argument("--validate", action="store_true",
                        help="Valida conformidad implementación vs spec (delega a vault_spec_validate)")
    parser.add_argument("--check",  action="store_true", help="Mostrar manifiesto sin escribir")
    parser.add_argument("--status", choices=["active", "deprecated", "internal", "meta"],
                        help="Filtrar por estado")

    args = parser.parse_args()

    # ── Modo bootstrap ──────────────────────────────────────────────────────
    if args.bootstrap:
        spec = _bootstrap_spec()
        # v39/AP-36: el contrato vive en <vault>/00_System/ y se escribe de forma
        # atómica. Antes: scripts/tool-spec.json con write_text() directo.
        spec_file = tool_spec_path()
        atomic_write_json(spec_file, spec)
        tool_count = len(spec["tools"])
        active = sum(1 for e in spec["tools"].values() if e["status"] == "active")
        print(json.dumps({
            "ok": True,
            "action": "bootstrap",
            "spec_file": str(spec_file.relative_to(get_vault_root())).replace("\\", "/"),
            "tools_total": tool_count,
            "tools_active": active,
            "version": spec["version"],
            "next_step": "Commit tool-spec.json. Desde ahora editar spec ANTES de implementar.",
        }, indent=2, ensure_ascii=False))
        return 0

    # ── Modo validate ──────────────────────────────────────────────────────
    if args.validate:
        try:
            from vault_spec_validate import load_spec, run_validation, _print_report
            spec = load_spec()
            validation = run_validation(spec)
            _print_report(validation)
            return 0 if validation["ok"] else 1
        except ImportError:
            print(json.dumps({"ok": False, "error": "vault_spec_validate.py no encontrado"}))
            return 1

    # ── Modo normal (genera manifiesto) ────────────────────────────────────
    spec = _load_spec()
    if spec is not None:
        manifest = _build_manifest_from_spec(spec)
        source_label = "tool-spec.json"
    else:
        # Fallback hardcodeado — advertir
        import sys as _sys
        print(
            '{"warning": "tool-spec.json no encontrado — usando datos hardcodeados. '
            'Ejecutar: python vault_manifest.py --bootstrap"}',
            file=_sys.stderr,
        )
        manifest = _build_manifest()
        source_label = "hardcoded (fallback)"

    if args.status:
        manifest = [e for e in manifest if e["status"] == args.status]

    result: Dict[str, Any] = {
        "ok": True,
        "standard_version": _read_version(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source_label,
        "total":      len(manifest),
        "active":     sum(1 for e in manifest if e["status"] == "active"),
        "deprecated": sum(1 for e in manifest if e["status"] == "deprecated"),
        "internal":   sum(1 for e in manifest if e["status"] == "internal"),
        "meta":       sum(1 for e in manifest if e["status"] == "meta"),
        "tools": manifest,
    }

    if args.check:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    _system_dir().mkdir(parents=True, exist_ok=True)
    _manifest_file().write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "source": source_label,
        "total":      result["total"],
        "active":     result["active"],
        "deprecated": result["deprecated"],
        "path": str(_manifest_file().relative_to(_raiz())).replace("\\", "/"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_manifest"))
