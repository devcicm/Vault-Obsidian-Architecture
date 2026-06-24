#!/usr/bin/env python3
"""
vault_compact_contracts.py — Genera contratos compactos de las 57 vault tools activas.

Lee cada script via introspección de argparse + docstring y genera:
  - 00_System/tool-contracts.json  (machine-readable, ~250 líneas)
  - 00_System/tool-contracts.md    (human-readable, tabla por grupo)

El agente puede cargar tool-contracts.json en lugar del spec completo.

Usage:
    python vault_compact_contracts.py                      # genera ambos archivos (perfil actual)
    python vault_compact_contracts.py --profile minimal    # solo las 10 tools core
    python vault_compact_contracts.py --profile standard   # 30 tools
    python vault_compact_contracts.py --profile full       # las 57 tools activas
    python vault_compact_contracts.py --check              # muestra contratos sin escribir
"""

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from vault_errors import wrap_main

SCRIPTS_DIR = Path(__file__).parent

from vault_io import VAULT_ROOT  # noqa: E402

SYSTEM_DIR = VAULT_ROOT / "00_System"
CONTRACTS_JSON = SYSTEM_DIR / "tool-contracts.json"
CONTRACTS_MD = SYSTEM_DIR / "tool-contracts.md"
VERSION_FILE = SYSTEM_DIR / "standard-version.json"

# ──────────────────────────────────────────────────────────────────────────────
# Group metadata — leído desde tool-spec.json (spec-driven).
# Fallback al hardcodeado si el spec no existe aún.
# ──────────────────────────────────────────────────────────────────────────────

_SPEC_FILE = SCRIPTS_DIR / "tool-spec.json"

_GROUPS_HARDCODED: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Core",
        "tools": [
            "vault_write",
            "vault_read",
            "vault_search",
            "vault_list",
            "vault_append",
            "vault_diff",
            "vault_merge",
        ],
    },
    {"id": 2, "name": "Observabilidad", "tools": ["vault_log_error"]},
    {
        "id": 3,
        "name": "Patrones",
        "tools": ["vault_pattern_save", "vault_pattern_list"],
    },
    {
        "id": 4,
        "name": "Diagramas",
        "tools": ["vault_diagram_save", "vault_relation_add"],
    },
    {
        "id": 5,
        "name": "Conocimiento",
        "tools": ["vault_knowledge_save", "vault_knowledge_get"],
    },
    {
        "id": 6,
        "name": "Salud",
        "tools": ["vault_audit", "vault_validate", "vault_graph"],
    },
    {"id": 7, "name": "Runbooks", "tools": ["vault_runbook_save", "vault_runbook_log"]},
    {
        "id": 8,
        "name": "Infraestructura",
        "tools": ["vault_infra_save", "vault_infra_map", "vault_env_save"],
    },
    {
        "id": 9,
        "name": "Migración",
        "tools": ["vault_migrate_docs", "vault_migrate_rollback"],
    },
    {"id": 10, "name": "Línea de tiempo", "tools": ["vault_timeline"]},
    {
        "id": 11,
        "name": "Vista proyecto",
        "tools": ["vault_project_status", "vault_project_overview"],
    },
    {
        "id": 12,
        "name": "Código",
        "tools": [
            "vault_code_module",
            "vault_code_relation",
            "vault_code_map",
            "vault_code_query",
        ],
    },
    {
        "id": 13,
        "name": "Backups",
        "tools": ["vault_backup", "vault_backup_list", "vault_restore"],
    },
    {"id": 14, "name": "Seguridad", "tools": ["vault_security_scan"]},
    {
        "id": 15,
        "name": "Índices",
        "tools": ["vault_section_index", "vault_master_index", "vault_reindex"],
    },
    {"id": 16, "name": "Bibliografía", "tools": ["vault_bibliography_save"]},
    {"id": 17, "name": "Drift", "tools": ["vault_drift_detect"]},
    {"id": 18, "name": "Flujos", "tools": ["vault_flow_save"]},
    {"id": 19, "name": "Requerimientos", "tools": ["vault_requirement_save"]},
    {"id": 20, "name": "Tests", "tools": ["vault_test_save"]},
    {"id": 21, "name": "IA Governance", "tools": ["vault_ai_decision"]},
    {
        "id": 22,
        "name": "Versionado",
        "tools": ["vault_standard_upgrade", "vault_onboard"],
    },
    {"id": 23, "name": "Change Log", "tools": ["vault_change_log"]},
    {
        "id": 24,
        "name": "Data Quality",
        "tools": ["vault_quality_check", "vault_fundamentals"],
    },
    {"id": 25, "name": "Propagación", "tools": ["vault_impact", "vault_propagate"]},
    {
        "id": 26,
        "name": "Tokens",
        "tools": ["vault_tokens", "vault_token_counter", "vault_token_service"],
    },
    {"id": 27, "name": "Session Delta y Tags", "tools": ["vault_delta", "vault_tags"]},
    {
        "id": 28,
        "name": "Normas y Etiquetas",
        "tools": ["vault_norms", "vault_code_tag"],
    },
    {
        "id": 29,
        "name": "Producción y SRE",
        "tools": ["vault_incident_save", "vault_slo_save"],
    },
    {
        "id": 30,
        "name": "Release y Entornos",
        "tools": ["vault_env_matrix", "vault_release_save"],
    },
    {
        "id": 31,
        "name": "Riesgos y Calidad",
        "tools": ["vault_risk_save", "vault_privacy_save", "vault_ncr_save"],
    },
]


_TOOL_SPEC: Dict[str, Any] = {}


def _load_tool_spec() -> Dict[str, Any]:
    """Carga tool-spec.json completo para obtener declared_returns."""
    if not _SPEC_FILE.exists():
        return {}
    try:
        return json.loads(_SPEC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_groups() -> List[Dict[str, Any]]:
    """Reconstruye la lista GROUPS desde tool-spec.json. Fallback a hardcoded."""
    global _TOOL_SPEC
    _TOOL_SPEC = _load_tool_spec()
    if not _TOOL_SPEC:
        return _GROUPS_HARDCODED
    try:
        by_group: Dict[int, Dict[str, Any]] = {}
        for name, entry in _TOOL_SPEC.get("tools", {}).items():
            gid = entry.get("group_id", 0)
            gname = entry.get("group", "misc")
            if gid not in by_group:
                by_group[gid] = {"id": gid, "name": gname, "tools": []}
            by_group[gid]["tools"].append(name)
        return sorted(by_group.values(), key=lambda g: g["id"]) or _GROUPS_HARDCODED
    except Exception:
        return _GROUPS_HARDCODED


GROUPS: List[Dict[str, Any]] = _load_groups()

# Build tool → group lookup
_TOOL_GROUP: Dict[str, Dict] = {}
for g in GROUPS:
    for t in g["tools"]:
        _TOOL_GROUP[t] = g

# ──────────────────────────────────────────────────────────────────────────────
# Profile definitions
# ──────────────────────────────────────────────────────────────────────────────

PROFILES: Dict[str, List[str]] = {
    "minimal": [
        "vault_write",
        "vault_read",
        "vault_search",
        "vault_list",
        "vault_append",
        "vault_audit",
        "vault_reindex",
        "vault_change_log",
        "vault_standard_upgrade",
        "vault_errors",
    ],
    "standard": [
        "vault_write",
        "vault_read",
        "vault_search",
        "vault_list",
        "vault_append",
        "vault_diff",
        "vault_merge",
        "vault_validate",
        "vault_graph",
        "vault_log_error",
        "vault_pattern_save",
        "vault_pattern_list",
        "vault_knowledge_save",
        "vault_knowledge_get",
        "vault_diagram_save",
        "vault_relation_add",
        "vault_runbook_save",
        "vault_runbook_log",
        "vault_infra_save",
        "vault_env_save",
        "vault_project_status",
        "vault_project_overview",
        "vault_code_module",
        "vault_backup",
        "vault_backup_list",
        "vault_restore",
        "vault_section_index",
        "vault_master_index",
        "vault_reindex",
        "vault_drift_detect",
        "vault_security_scan",
        "vault_timeline",
        "vault_bibliography_save",
        "vault_flow_save",
        "vault_migrate_docs",
        "vault_migrate_rollback",
        "vault_change_log",
        "vault_standard_upgrade",
        "vault_audit",
    ],
}
# full = all tools with vault_ prefix (discovered dynamically)


# ──────────────────────────────────────────────────────────────────────────────
# Introspection
# ──────────────────────────────────────────────────────────────────────────────


def _get_docstring(source: str) -> str:
    """Extract module-level docstring from source."""
    try:
        tree = ast.parse(source)
        return ast.get_docstring(tree) or ""
    except Exception:
        return ""


def _extract_argparse_args(source: str) -> tuple:
    """
    Heuristic extraction of argparse arguments from source text.
    Returns (required_args, optional_args) as lists of dicts.
    """
    required, optional = [], []
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "add_argument(" in line:
            # Collect full call (may span multiple lines)
            call = line
            depth = call.count("(") - call.count(")")
            j = i + 1
            while depth > 0 and j < len(lines):
                call += " " + lines[j].strip()
                depth += lines[j].count("(") - lines[j].count(")")
                j += 1

            # Extract flag name
            name_match = None
            import re

            names = re.findall(r"""add_argument\(\s*["']([^"']+)["']""", call)
            if not names:
                i += 1
                continue
            flag = names[0]
            if flag.startswith("-"):
                name = flag.lstrip("-").replace("-", "_")
            else:
                name = flag

            # Required?
            is_required = "required=True" in call or (not flag.startswith("-"))
            is_store_true = "store_true" in call or "store_false" in call

            # Help text
            help_match = re.search(r"""help=["']([^"']{0,120})""", call)
            help_text = help_match.group(1) if help_match else ""

            # Type
            type_match = re.search(r"type=(\w+)", call)
            arg_type = (
                type_match.group(1)
                if type_match
                else ("bool" if is_store_true else "str")
            )

            entry = {"name": name, "flag": flag, "type": arg_type, "help": help_text}
            if is_required:
                required.append(entry)
            else:
                optional.append(entry)
        i += 1

    return required, optional


def introspect_tool(name: str) -> Optional[Dict[str, Any]]:
    """Introspect a vault script and return its contract dict."""
    path = SCRIPTS_DIR / f"{name}.py"
    if not path.exists():
        return None

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    doc = _get_docstring(source)
    description = ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            description = line
            break

    required_args, optional_args = _extract_argparse_args(source)

    group = _TOOL_GROUP.get(name, {})

    deprecated = "_deprecation" in source

    # Build explicit command
    cmd_parts = [f"python scripts/{name}.py"]
    for arg in required_args:
        flag = arg["flag"]
        cmd_parts.append(f"{flag} <{arg['name']}>")
    command = " ".join(cmd_parts)

    # Get declared_returns from tool-spec.json
    declared_returns = []
    if _TOOL_SPEC and name in _TOOL_SPEC.get("tools", {}):
        declared_returns = _TOOL_SPEC["tools"][name].get("declared_returns", [])

    return {
        "name": name,
        "group_id": group.get("id", 0),
        "group": group.get("name", "misc"),
        "description": description,
        "required_args": required_args,
        "optional_args": optional_args,
        "deprecated": deprecated,
        "script": f"scripts/{name}.py",
        "command": command,
        "returns": declared_returns,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Profile resolution
# ──────────────────────────────────────────────────────────────────────────────


def _read_current_profile() -> str:
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        return data.get("profile", "full")
    except Exception:
        return "full"


def _resolve_tool_list(profile: str) -> List[str]:
    if profile == "minimal":
        return PROFILES["minimal"]
    if profile == "standard":
        return PROFILES["standard"]
    # full: all vault_*.py scripts (excluding vault_errors and internal helpers)
    all_scripts = sorted(
        p.stem
        for p in SCRIPTS_DIR.glob("vault_*.py")
        if p.stem
        not in (
            "vault_errors",
            "vault_test_runner",
            "vault_compact_contracts",
            "vault_manifest",
        )
    )
    return all_scripts


# ──────────────────────────────────────────────────────────────────────────────
# Output generators
# ──────────────────────────────────────────────────────────────────────────────


def _generate_contracts(tool_names: List[str]) -> List[Dict[str, Any]]:
    contracts = []
    for name in tool_names:
        contract = introspect_tool(name)
        if contract:
            contracts.append(contract)
    # Sort by group_id then name
    contracts.sort(key=lambda c: (c["group_id"], c["name"]))
    return contracts


def _contracts_to_md(contracts: List[Dict[str, Any]], profile: str) -> str:
    lines = [
        "# Tool Contracts",
        "",
        f"**Perfil:** `{profile}` | **Tools:** {len(contracts)}",
        "",
        "_Generado automáticamente por vault_compact_contracts.py_",
        "",
    ]

    current_group = None
    for c in contracts:
        if c["group"] != current_group:
            current_group = c["group"]
            lines.append(f"\n## Grupo {c['group_id']} — {c['group']}\n")
            lines.append("| Tool | Descripción | Comando | Output |")
            lines.append("|---|---|---|---|")

        dep_tag = " *(deprecated)*" if c.get("deprecated") else ""
        cmd = c.get("command", f"python scripts/{c['name']}.py")
        output = ", ".join(c.get("returns", [])) or "—"
        lines.append(
            f"| `{c['name']}`{dep_tag} | {c['description'][:60]} | `{cmd}` | `{output}` |"
        )

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_compact_contracts -- genera tool-contracts.json y tool-contracts.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_compact_contracts.py                   # usa perfil guardado en standard-version.json
  python vault_compact_contracts.py --profile minimal # solo las 10 tools core
  python vault_compact_contracts.py --profile full    # las 53 tools
  python vault_compact_contracts.py --check           # muestra JSON sin escribir archivos
""",
    )
    parser.add_argument(
        "--profile",
        choices=["minimal", "standard", "full"],
        help="Perfil de tools a incluir (default: lee de 00_System/standard-version.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Solo mostrar contratos, no escribir archivos",
    )

    args = parser.parse_args()

    profile = args.profile or _read_current_profile()
    tool_names = _resolve_tool_list(profile)
    contracts = _generate_contracts(tool_names)

    result = {
        "ok": True,
        "profile": profile,
        "tool_count": len(contracts),
        "contracts": contracts,
    }

    if args.check:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # Write JSON
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACTS_JSON.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Write MD
    md_content = _contracts_to_md(contracts, profile)
    CONTRACTS_MD.write_text(md_content, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "profile": profile,
                "tool_count": len(contracts),
                "contracts_json": str(CONTRACTS_JSON.relative_to(VAULT_ROOT)).replace(
                    "\\", "/"
                ),
                "contracts_md": str(CONTRACTS_MD.relative_to(VAULT_ROOT)).replace(
                    "\\", "/"
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_compact_contracts"))
