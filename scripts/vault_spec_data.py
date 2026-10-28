#!/usr/bin/env python3
"""vault_spec_data — los datos del manifiesto, en una hoja (AP-58, v41.17).

`vault_manifest` y `vault_spec_memory` se importaban mutuamente con
imports diferidos dentro de funciones: dos ciclos AP-58 por fichero
(`vault_manifest->vault_spec_memory` y su vuelta). La inversión real no
era subir el import sino darle a los DATOS compartidos un dueño que no
necesite a ninguno de los dos:

- `DQ_METADATA`, `TOOL_GROUPS`, `_FUND_BY_TOOL` y `_build_manifest`
  vienen de `vault_manifest` (el derivador del manifiesto).
- `DECLARED_RETURNS` y su extractor vienen de `vault_spec_memory` (la
  memoria de contratos declarados por introspección de código).

Ambos módulos ahora importan esta hoja; la hoja no importa a ninguno.
Es datos + introspección pura: nada de vault, nada de runtime de tools.

Solo el nombre `vault_spec_data` es nuevo; los nombres Dueños se
reexportan desde `vault_manifest` para no romper consumidores (AP-48).
"""
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import emit_error
from vault_io import resolve_tool_spec

_RE_VAULT_SPEC_DATA_1 = re.compile('"error_code"\\s*:\\s*"([^"]+)"')
_RE_VAULT_SPEC_DATA_2 = re.compile("'error_code'\\s*:\\s*'([^']+)'")
_RE_VAULT_SPEC_DATA_3 = re.compile('error_code\\s*=\\s*["\\\']([^"\\\']+)["\\\']')

# El mismo SCRIPTS_DIR que usaban los dos módulos origen: la carpeta de
# scripts del checkout (los bloques de abajo lo consumen).
SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


DEPRECATED_TOOLS: Dict[str, Dict[str, str]] = {
    "vault_migrate":    {"replaced_by": "vault_migrate_docs",    "since": "v25", "reason": "vault_migrate_docs is the canonical migration tool with full project support"},
    "vault_reorganize": {"replaced_by": "vault_migrate_docs",    "since": "v25", "reason": "Dynamic dest detection is handled by vault_migrate_docs"},
    "vault_tools":      {"replaced_by": "See individual tools",  "since": "v22", "reason": "Monolithic script superseded by dedicated tools per group"},
    "vault_create":     {"replaced_by": "vault_write",           "since": "v21", "reason": "vault_write handles all note creation with AP guards"},
    "vault_render":     {"replaced_by": "vault_diagram_save",    "since": "v22", "reason": "vault_diagram_save generates Mermaid diagrams with ERD support"},
}

INTERNAL_TOOLS: List[str] = ["vault_release",
                            "vault_dataset", "vault_index", "vault_io",
                            "vault_link_safety",
                            # v41.12: arnés de alcance de tests. No es tool del
                            # catálogo — su consumidor es quien cierra un cambio
                            # aquí, no un vault— pero el repo exige clasificar
                            # todo script con CLI propia (AP-57: nada sin
                            # contrato) y `internal` es el estado con motivo.
                            "vault_test_scope"]

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

def _derive_fundamentals_by_tool() -> Dict[str, List[str]]:
    """Single source of truth: derive data_fundamentals per tool from vault_fundamentals registry."""
    try:
        from vault_fundamentals_catalog import FUNDAMENTALS as _FUNDS
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

def _load_declared_returns() -> Dict[str, List[str]]:
    """Carga declared_returns desde tool-spec.json. Fallback a hardcoded si no existe."""
    spec_file = resolve_tool_spec()
    if spec_file is not None:
        try:
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
            return {
                name: entry.get("declared_returns", [])
                for name, entry in spec.get("tools", {}).items()
            }
        except Exception:
            pass
    # Fallback hardcodeado (pre-spec-driven)
    return {
        "vault_write":            ["path", "id"],
        "vault_read":             ["path", "body"],
        "vault_search":           ["results"],
        "vault_list":             ["notes"],
        "vault_append":           ["path"],
        "vault_diff":             ["path", "changed"],
        "vault_merge":            ["action"],
        "vault_log_error":        [],
        "vault_pattern_save":     ["path"],
        "vault_pattern_list":     ["patterns"],
        "vault_diagram_save":     ["path"],
        "vault_relation_add":     ["path"],
        "vault_knowledge_save":   ["path"],
        "vault_knowledge_get":    ["results", "query", "total"],
        "vault_audit":            ["healthScore"],
        "vault_validate":         [],
        "vault_graph":            [],
        "vault_runbook_save":     ["path"],
        "vault_runbook_log":      [],
        "vault_infra_save":       ["path"],
        "vault_infra_map":        ["path", "nodesTotal"],
        "vault_env_save":         ["path"],
        "vault_migrate_docs":     [],
        "vault_migrate_rollback": [],
        "vault_timeline":         ["query"],
        "vault_project_status":   ["path"],
        "vault_project_overview": ["path"],
        "vault_code_module":      ["path"],
        "vault_code_relation":    [],
        "vault_code_map":         ["path"],
        "vault_code_query":       [],
        "vault_backup":           ["name", "path"],
        "vault_backup_list":      ["total"],
        "vault_restore":          [],
        "vault_security_scan":    ["riskLevel"],
        "vault_section_index":    ["path"],
        "vault_master_index":     ["path"],
        "vault_reindex":          ["indexed"],
        "vault_bibliography_save": ["path"],
        "vault_drift_detect":     ["mode"],
        "vault_flow_save":        ["path"],
        "vault_requirement_save": ["path"],
        "vault_test_save":        ["path"],
        "vault_ai_decision":      ["path"],
        "vault_standard_upgrade": [],
        "vault_change_log":       ["id"],
        "vault_quality_check":    [],
        "vault_fundamentals":     [],
        "vault_impact":           [],
        "vault_propagate":        [],
        "vault_tokens":           [],
        "vault_token_counter":    [],
        "vault_token_service":    [],
    }


DECLARED_RETURNS: Dict[str, List[str]] = _load_declared_returns()

# ──────────────────────────────────────────────────────────────────────────────
# Introspection helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_args(source: str):
    """Los argumentos del script en `(obligatorios, opcionales)`, leídos por
    `flags_cli`. Un posicional cuenta como obligatorio."""
    required, optional = [], []
    # AP-58: arista unidireccional, benigna. El dueño vive en el paquete
    # `vault`, y en una corrida como script (o un test que traiga solo
    # `scripts/` al path) la raíz del repo no está: se garantiza aquí, antes
    # del import diferido.
    _raiz_repo = Path(__file__).resolve().parent.parent
    if str(_raiz_repo) not in sys.path:
        sys.path.insert(0, str(_raiz_repo))
    from vault.meta_toolkit import flags_cli  # noqa: E402  (AP-58: diferido)
    for d in flags_cli.declaraciones(source):
        flag = d.nombres[0]
        name = flag.lstrip("-").replace("-", "_") if flag.startswith("-") else flag
        tipo = d.kw.get("type")
        if isinstance(tipo, ast.Name):
            arg_type = tipo.id
        elif d.accion in ("store_true", "store_false"):
            arg_type = "bool"
        else:
            arg_type = "str"
        ayuda = d.constante("help")
        entry = {"name": name, "flag": flag, "type": arg_type,
                 "help": ayuda[:120] if isinstance(ayuda, str) else ""}
        (required if d.obligatorio or d.posicional else optional).append(entry)
    return required, optional


def _extract_error_codes(source: str) -> List[str]:
    """Grep source for declared error_code strings."""
    codes: Set[str] = set()
    for m in _RE_VAULT_SPEC_DATA_1.finditer(source):
        codes.add(m.group(1))
    for m in _RE_VAULT_SPEC_DATA_2.finditer(source):
        codes.add(m.group(1))
    # Also catch error_code as variable assignment: error_code = "..."
    for m in _RE_VAULT_SPEC_DATA_3.finditer(source):
        codes.add(m.group(1))
    return sorted(codes)


def _read_source(name: str) -> Optional[str]:
    # Deuda #12: `scripts/<name>.py` puede ser un alias sin código; la fuente
    # es la del dueño (AP-44). Sin alias, `fuente_de` devuelve `scripts/<name>.py`.
    import vault_grafo_import  # AP-58: arista unidireccional, benigna
    p = vault_grafo_import.fuente_de(name)
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
    except Exception:
        return None
