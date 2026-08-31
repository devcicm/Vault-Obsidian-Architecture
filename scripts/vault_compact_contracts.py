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
from vault_errors import emit_error, wrap_main

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

from vault_io import resolve_tool_spec  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT))

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402
# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones


def _repo(root=None) -> RepositorioConsulta:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioConsulta(construir(root))


def _resolve_output_dir() -> Path:
    """Resolve output directory for contracts.

    If running from spec repo (has vault-obsidian-architecture.md), write to vault-sandbox.
    Otherwise write to the consumer vault's `00_System`.

    Esta función era la forma cara de AP-49: el guard no la veía —no deriva de
    la raíz en una asignación— pero `SYSTEM_DIR = _resolve_output_dir()`
    se evaluaba igual al importar. Parecía resolución tardía y no lo era.
    """
    if (PROJECT_ROOT / "vault-obsidian-architecture.md").exists():
        sandbox = PROJECT_ROOT / "vault-sandbox" / "00_System"
        if sandbox.exists():
            return sandbox
    return _repo().dir_sistema


def _system_dir() -> Path:
    return _resolve_output_dir()


def _contracts_json() -> Path:
    return _system_dir() / "tool-contracts.json"


def _contracts_md() -> Path:
    return _system_dir() / "tool-contracts.md"


def _version_file() -> Path:
    return _system_dir() / "standard-version.json"

# ──────────────────────────────────────────────────────────────────────────────
# Group metadata — leído desde tool-spec.json, que es la proyección del catálogo
# que `vault_mcp_catalog --check-contracts` ya vigila (`group` y `group_id` se
# derivan de `GROUPS` y de la numeración de `scripts/README.md`).
#
# superseded_by: _grupos()
#
# `_GROUPS_HARDCODED` era la segunda copia del catálogo y no se deroga —se
# conserva su contenido como estaba—, pero deja de ser fuente de nada. Lo era
# de tres maneras a la vez y todas silenciosas: se había quedado en 31 grupos
# frente a los 37 canónicos, se elegía dentro de un `except Exception` que se
# tragaba cualquier fallo de lectura, y `GROUPS` se calculaba en tiempo de
# import (AP-49) contra el vault que estuviera detectado en ese momento, así
# que `set_vault_root()` no podía cambiarlo. Un vault sin `tool-spec.json`
# obtenía un catálogo de hace seis grupos sin que nada lo dijera.
# ──────────────────────────────────────────────────────────────────────────────

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


#: Memoria por ruta de spec, no por proceso: `set_vault_root()` cambia la ruta
#: y con ella la entrada, que es justo lo que el binding en import impedía.
_SPEC_CACHE: Dict[str, Dict[str, Any]] = {}


def _tool_spec() -> Dict[str, Any]:
    """El `tool-spec.json` del vault activo, resuelto al usarse (AP-49).

    Un fallo de lectura ya no devuelve `{}` en silencio: un spec ilegible es un
    defecto del vault, y taparlo hacía que las tools salieran sin
    `declared_returns` y sin grupo como si eso fuera normal.
    """
    spec_file = resolve_tool_spec()
    if spec_file is None:
        raise FileNotFoundError(
            "No hay tool-spec.json en el vault activo. Es la fuente de "
            "`group`, `group_id` y `declared_returns`; sin él no hay contrato "
            "que compactar. Genéralo con `vault_mcp_catalog --sync`."
        )
    clave = str(spec_file)
    if clave not in _SPEC_CACHE:
        _SPEC_CACHE[clave] = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    return _SPEC_CACHE[clave]


def _grupos() -> List[Dict[str, Any]]:
    """Los grupos, derivados del spec y no de una copia local.

    `group` y `group_id` de cada entrada los deriva `vault_mcp_catalog` de
    `GROUPS` y de la numeración de `scripts/README.md`, y su
    `--check-contracts` falla si divergen. Reconstruir aquí la agrupación a
    partir del spec es leer esa misma decisión, no tomarla otra vez.
    """
    por_grupo: Dict[int, Dict[str, Any]] = {}
    for name, entry in _tool_spec().get("tools", {}).items():
        gid = entry.get("group_id", 0)
        por_grupo.setdefault(
            gid, {"id": gid, "name": entry.get("group", "misc"), "tools": []}
        )["tools"].append(name)
    return sorted(por_grupo.values(), key=lambda g: g["id"])


def __getattr__(nombre: str):
    """`GROUPS` sigue existiendo como símbolo, pero se resuelve al leerse.

    No-derogación: `vault_manifest` hace `from vault_compact_contracts import
    GROUPS` y ese contrato se conserva intacto. Lo que cambia es *cuándo* se
    calcula. Como constante de módulo quedaba fijada contra el vault detectado
    en el import (AP-49); vía `__getattr__` la lee quien la pide, cuando la
    pide, contra el vault que esté activo entonces.
    """
    if nombre == "GROUPS":
        return _grupos()
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def _grupo_de(nombre: str) -> Dict[str, Any]:
    """A qué grupo pertenece una tool. Resuelto al usarse."""
    for g in _grupos():
        if nombre in g["tools"]:
            return g
    return {}

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
    except SyntaxError:
        return ""
    except Exception as exc:
        emit_error("vault_compact_contracts", "AST_PARSE_ERROR", str(exc))
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
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        emit_error("vault_compact_contracts", "FILE_READ_ERROR", str(exc))
        return None
    except Exception as exc:
        emit_error("vault_compact_contracts", "UNEXPECTED_ERROR", str(exc))
        return None

    doc = _get_docstring(source)
    description = ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            description = line
            break

    required_args, optional_args = _extract_argparse_args(source)

    group = _grupo_de(name)

    deprecated = "_deprecation" in source

    # Build explicit command
    cmd_parts = [f"python scripts/{name}.py"]
    for arg in required_args:
        flag = arg["flag"]
        cmd_parts.append(f"{flag} <{arg['name']}>")
    command = " ".join(cmd_parts)

    # Get declared_returns from tool-spec.json
    declared_returns = _tool_spec().get("tools", {}).get(name, {}).get(
        "declared_returns", []
    )

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
        data = json.loads(_version_file().read_text(encoding="utf-8"))
        return data.get("profile", "full")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        emit_error("vault_compact_contracts", "PROFILE_READ_ERROR", str(exc))
        return "full"
    except Exception as exc:
        emit_error("vault_compact_contracts", "UNEXPECTED_ERROR", str(exc))
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
        choices=_opciones("detalle"),
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
    _system_dir().mkdir(parents=True, exist_ok=True)
    _contracts_json().write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Write MD
    md_content = _contracts_to_md(contracts, profile)
    _contracts_md().write_text(md_content, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "profile": profile,
                "tool_count": len(contracts),
                "contracts_json": str(_contracts_json().relative_to(_repo().raiz)).replace(
                    "\\", "/"
                ),
                "contracts_md": str(_contracts_md().relative_to(_repo().raiz)).replace(
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
