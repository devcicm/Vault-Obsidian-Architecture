#!/usr/bin/env python3
"""
vault_spec_memory.py — Unified spec-driven memory for the vault standard.

Combines in a single document:
  - Tool contracts (required args, optional args, returns, error codes)
  - DQ / CIA metadata per tool (from vault_manifest)
  - Data Fundamentals spec F1-F8 (from vault_fundamentals)
  - Traceability index: fundamental → tools → tests
  - System memory: DQ health, propagation pending, recent changes
  - Project tracking: pending issues, spec drift

Writes 00_System/spec-memory.json — the agent's canonical working memory.
The agent can load this single file instead of querying 6+ separate indexes.

Modes:
    python vault_spec_memory.py               # generate spec-memory.json
    python vault_spec_memory.py --check       # show without writing
    python vault_spec_memory.py --validate    # run tests + update test_status per tool
    python vault_spec_memory.py --tool NAME   # show single tool's full spec entry
    python vault_spec_memory.py --summary     # print human-readable dashboard
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

SCRIPTS_DIR = Path(__file__).parent

from vault_errors import wrap_main
from vault_io import resolve_tool_spec  # noqa: E402
PYTHON = sys.executable

# ──────────────────────────────────────────────────────────────────────────────
# Declared returns per tool — leídos desde tool-spec.json (spec-driven).
# Fallback al dict hardcodeado si el archivo de spec no existe aún.
# Fuente canónica: <vault>/00_System/tool-spec.json (editar antes de implementar).
# ──────────────────────────────────────────────────────────────────────────────


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
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


def _spec_memory_file() -> Path:
    return _repo().memoria_spec


# ── Rutas ajenas: se piden a su contexto, no se vuelven a derivar ────────────
# Los cuatro ficheros siguientes se LEEN aqui y los escriben otros. Derivarlos
# por cuenta propia era AP-05 multiplicado: `quality-index.json` llego a
# calcularse en cuatro modulos de tres contextos, y el dia que se moviera solo
# se habrian enterado los que lo escriben.


def _quality_index() -> Path:
    return RepositorioGobernanza(construir()).indice_calidad


def _propagation_queue() -> Path:
    return RepositorioGobernanza(construir()).cola_propagacion


def _change_log() -> Path:
    return RepositorioGobernanza(construir()).bitacora_cambios


def _standard_version_file() -> Path:
    return RepositorioCicloDeVida(construir()).fichero_version


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
    """Extract required and optional argparse args from source."""
    required, optional = [], []
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
            if not names:
                i += 1
                continue
            flag = names[0]
            name = flag.lstrip("-").replace("-", "_") if flag.startswith("-") else flag
            is_required = "required=True" in call or not flag.startswith("-")
            is_bool = "store_true" in call or "store_false" in call
            type_match = re.search(r"type=(\w+)", call)
            arg_type = type_match.group(1) if type_match else ("bool" if is_bool else "str")
            help_match = re.search(r"""help=["']([^"']{0,120})""", call)
            help_text = help_match.group(1) if help_match else ""
            entry = {"name": name, "flag": flag, "type": arg_type, "help": help_text}
            (required if is_required else optional).append(entry)
        i += 1
    return required, optional


def _extract_error_codes(source: str) -> List[str]:
    """Grep source for declared error_code strings."""
    codes: Set[str] = set()
    for m in re.finditer(r'"error_code"\s*:\s*"([^"]+)"', source):
        codes.add(m.group(1))
    for m in re.finditer(r"'error_code'\s*:\s*'([^']+)'", source):
        codes.add(m.group(1))
    # Also catch error_code as variable assignment: error_code = "..."
    for m in re.finditer(r'error_code\s*=\s*["\']([^"\']+)["\']', source):
        codes.add(m.group(1))
    return sorted(codes)


def _read_source(name: str) -> Optional[str]:
    p = SCRIPTS_DIR / f"{name}.py"
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
    except Exception:
        return None


def _get_description(source: str) -> str:
    """First non-empty line of module docstring."""
    try:
        import ast
        tree = ast.parse(source)
        doc = ast.get_docstring(tree) or ""
        for line in doc.splitlines():
            line = line.strip()
            if line:
                return line
    except Exception:
        pass
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# System memory readers
# ──────────────────────────────────────────────────────────────────────────────

def _read_dq_memory() -> Dict[str, Any]:
    try:
        data = json.loads(_quality_index().read_text(encoding="utf-8"))
        return {
            "overall_score": data.get("overall_dq_score"),
            "notes_below_threshold": len([
                v for v in data.get("notes", {}).values()
                if isinstance(v, dict) and v.get("overall", 1.0) < 0.7
            ]),
            "threshold": 0.7,
            "last_run": data.get("generated_at"),
            "generated_by": data.get("generated_by", "vault_quality_check"),
            "status": "available",
        }
    except FileNotFoundError:
        return {"status": "not_generated", "overall_score": None, "last_run": None}
    except Exception as e:
        return {"status": "error", "error": str(e), "overall_score": None}


def _read_propagation_memory() -> Dict[str, Any]:
    try:
        data = json.loads(_propagation_queue().read_text(encoding="utf-8"))
        pending = data.get("pending", [])
        high = [p for p in pending if p.get("priority") == "high"]
        return {
            "pending_count": len(pending),
            "high_priority": len(high),
            "updated_at": data.get("updated_at"),
            "top_pending": [
                {"path": p["path"], "priority": p.get("priority"), "distance": p.get("distance")}
                for p in pending[:5]
            ],
            "status": "available",
        }
    except FileNotFoundError:
        return {"status": "empty", "pending_count": 0, "high_priority": 0}
    except Exception as e:
        return {"status": "error", "error": str(e), "pending_count": 0}


def _read_change_memory() -> Dict[str, Any]:
    try:
        data = json.loads(_change_log().read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        recent = entries[-10:] if len(entries) > 10 else entries
        return {
            "total_changes": len(entries),
            "last_change": entries[-1].get("timestamp") if entries else None,
            "recent": [
                {"action": e.get("action"), "path": e.get("path"), "timestamp": e.get("timestamp")}
                for e in reversed(recent)
            ],
            "status": "available",
        }
    except FileNotFoundError:
        return {"status": "empty", "total_changes": 0, "last_change": None}
    except Exception as e:
        return {"status": "error", "error": str(e), "total_changes": 0}


def _read_standard_version() -> str:
    try:
        data = json.loads(_standard_version_file().read_text(encoding="utf-8"))
        v = data.get("version", "unknown")
        return f"v{v}" if isinstance(v, int) else str(v)
    except Exception:
        return "v27"


# ──────────────────────────────────────────────────────────────────────────────
# Validation loop
# ──────────────────────────────────────────────────────────────────────────────

def _run_validation() -> Dict[str, Any]:
    """Run vault_test_runner --contracts --errors and return results keyed by tool."""
    try:
        result = subprocess.run(
            [PYTHON, str(SCRIPTS_DIR / "vault_test_runner.py"), "--contracts", "--errors", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(SCRIPTS_DIR),
        )
        data = json.loads(result.stdout)
    except Exception as e:
        return {"ok": False, "error": str(e), "by_tool": {}}

    by_tool: Dict[str, str] = {}
    for mode in ("contracts", "errors"):
        mode_data = data.get("results", {}).get(mode, {})
        for err in mode_data.get("errors", []):
            tool = err.get("tool")
            if tool:
                by_tool[tool] = "fail"

    contracts_data = data.get("results", {}).get("contracts", {})
    for tc_name in [
        e for e in DECLARED_RETURNS.keys()
        if e not in by_tool
    ]:
        by_tool[tc_name] = "pass"

    return {
        "ok": data.get("ok", False),
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contracts_total": contracts_data.get("total", 0),
        "contracts_passed": contracts_data.get("passed", 0),
        "contracts_failed": contracts_data.get("failed", 0),
        "by_tool": by_tool,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Core builder
# ──────────────────────────────────────────────────────────────────────────────

def build_spec_memory(validate: bool = False) -> Dict[str, Any]:
    from vault_manifest import _build_manifest, DQ_METADATA, _FUND_BY_TOOL  # type: ignore
    from vault_fundamentals import FUNDAMENTALS  # type: ignore

    manifest_entries = _build_manifest()
    version = _read_standard_version()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Run validation if requested
    validation = _run_validation() if validate else {"ok": None, "by_tool": {}, "ran_at": None}
    test_by_tool = validation.get("by_tool", {})

    # ── Traceability index: F-id → [tool names] ────────────────────────────
    traceability: Dict[str, List[str]] = {}
    for f in FUNDAMENTALS:
        traceability[f["id"]] = sorted(f.get("tools", []))

    # ── Build per-tool spec entries ─────────────────────────────────────────
    tools: Dict[str, Any] = {}
    active_count = deprecated_count = internal_count = meta_count = 0
    unannotated: List[str] = []
    spec_drift: List[Dict] = []

    for entry in manifest_entries:
        name = entry["name"]
        status = entry["status"]

        if status == "active":
            active_count += 1
        elif status == "deprecated":
            deprecated_count += 1
        elif status == "internal":
            internal_count += 1
        elif status == "meta":
            meta_count += 1

        source = _read_source(name)
        required_args, optional_args = ([], [])
        error_codes: List[str] = []
        description = ""

        if source:
            required_args, optional_args = _extract_args(source)
            error_codes = _extract_error_codes(source)
            description = _get_description(source)

        # Contract
        declared_returns = DECLARED_RETURNS.get(name, [])
        test_status = test_by_tool.get(name, "untested")

        contract: Dict[str, Any] = {
            "description": description,
            "required_args": [a["flag"] for a in required_args],
            "optional_args": [a["flag"] for a in optional_args],
            "returns": declared_returns,
            "error_codes": error_codes,
            "test_status": test_status,
        }

        # DQ / CIA
        dq = DQ_METADATA.get(name, {})
        fundamentals = _FUND_BY_TOOL.get(name, [])

        if status == "active" and not dq:
            unannotated.append(name)

        # Spec drift: active + annotated + test failed
        if status == "active" and validate and test_status == "fail":
            spec_drift.append({"tool": name, "status": "fail", "group": entry.get("group")})

        tool_entry: Dict[str, Any] = {
            "status": status,
            "group": entry.get("group", "misc"),
            "contract": contract,
        }

        if dq:
            tool_entry["dq"] = {
                "dimensions": dq.get("dq_dimensions", []),
                "cia_scope": dq.get("cia_scope", []),
                "propagation_aware": dq.get("propagation_aware", False),
            }
            if dq.get("is_registry"):
                tool_entry["dq"]["is_registry"] = True

        if fundamentals:
            tool_entry["fundamentals"] = fundamentals

        if status == "deprecated":
            tool_entry["replaced_by"] = entry.get("replaced_by")
            tool_entry["deprecated_since"] = entry.get("deprecated_since")

        tools[name] = tool_entry

    # ── Fundamentals spec ───────────────────────────────────────────────────
    fundamentals_spec: Dict[str, Any] = {}
    for f in FUNDAMENTALS:
        fundamentals_spec[f["id"]] = {
            "name": f["name"],
            "english": f["english"],
            "description": f["description"],
            "dq_dimension": f["dq_dimension"],
            "frontmatter_fields": f.get("frontmatter_fields", []),
            "tools": f.get("tools", []),
            "verifies": f.get("verifies", []),
        }

    # ── System memory ───────────────────────────────────────────────────────
    dq_mem = _read_dq_memory()
    prop_mem = _read_propagation_memory()
    change_mem = _read_change_memory()

    memory: Dict[str, Any] = {
        "dq_health": dq_mem,
        "propagation": prop_mem,
        "recent_activity": change_mem,
        "project_health": {
            "spec_drift": spec_drift,
            "unannotated_active": unannotated,
            "validation_ran": validate,
            "validation_at": validation.get("ran_at"),
        },
    }

    # ── Surface summary ─────────────────────────────────────────────────────
    with_fundamentals = sum(1 for t in tools.values() if t.get("fundamentals"))
    with_dq = sum(1 for t in tools.values() if t.get("dq") and t["status"] == "active")
    propagation_tools = sum(
        1 for t in tools.values()
        if t.get("dq", {}).get("propagation_aware") and t["status"] == "active"
    )

    return {
        "meta": {
            "schema": "spec-memory/v1",
            "standard_version": version,
            "generated_at": now,
            "generated_by": "vault_spec_memory",
            "validated": validate,
        },
        "surface": {
            "total": len(tools),
            "active": active_count,
            "deprecated": deprecated_count,
            "internal": internal_count,
            "meta": meta_count,
            "with_dq_annotation": with_dq,
            "with_fundamentals": with_fundamentals,
            "propagation_aware": propagation_tools,
            "coverage_pct": round(with_dq / active_count * 100, 1) if active_count else 0,
        },
        "spec": {
            "fundamentals": fundamentals_spec,
            "traceability": traceability,
        },
        "tools": tools,
        "memory": memory,
        "validation": {
            "last_run": validation.get("ran_at"),
            "contracts_total": validation.get("contracts_total", 0),
            "contracts_passed": validation.get("contracts_passed", 0),
            "contracts_failed": validation.get("contracts_failed", 0),
            "spec_drift_count": len(spec_drift),
        } if validate else {"last_run": None, "status": "not_run"},
    }


# ──────────────────────────────────────────────────────────────────────────────
# Human-readable summary
# ──────────────────────────────────────────────────────────────────────────────

def _print_summary(doc: Dict[str, Any]) -> None:
    meta = doc["meta"]
    surface = doc["surface"]
    mem = doc["memory"]
    val = doc.get("validation", {})

    print(f"\n{'='*60}")
    print(f"  VAULT SPEC-MEMORY — {meta['standard_version']} — {meta['generated_at']}")
    print(f"{'='*60}")

    print(f"\n[TOOL SURFACE]")
    print(f"  Total:      {surface['total']} scripts")
    print(f"  Active:     {surface['active']} tools")
    print(f"  Deprecated: {surface['deprecated']}  |  Internal: {surface['internal']}  |  Meta: {surface['meta']}")
    print(f"  DQ annotation:    {surface['with_dq_annotation']}/{surface['active']} ({surface['coverage_pct']}%)")
    print(f"  With fundamentals: {surface['with_fundamentals']}/{surface['active']}")
    print(f"  Propagation-aware: {surface['propagation_aware']}/{surface['active']}")

    print(f"\n[DATA FUNDAMENTALS]")
    for fid, f in doc["spec"]["fundamentals"].items():
        n_tools = len(f["tools"])
        print(f"  {fid} {f['name']:20s} → {n_tools} tools: {', '.join(f['tools'][:4])}{'...' if n_tools > 4 else ''}")

    print(f"\n[SYSTEM MEMORY]")
    dq = mem["dq_health"]
    if dq.get("overall_score") is not None:
        print(f"  DQ Score:          {dq['overall_score']:.2f}  (below 0.7: {dq.get('notes_below_threshold', '?')} notes)")
        print(f"  DQ last run:       {dq.get('last_run', 'unknown')}")
    else:
        print(f"  DQ Score:          {dq['status']}")

    prop = mem["propagation"]
    print(f"  Propagation queue: {prop['pending_count']} pending ({prop.get('high_priority', 0)} high priority)")

    chg = mem["recent_activity"]
    print(f"  Change log:        {chg.get('total_changes', 0)} total  |  last: {chg.get('last_change', 'none')}")

    ph = mem["project_health"]
    drift = ph.get("spec_drift", [])
    unannotated = ph.get("unannotated_active", [])
    print(f"\n[PROJECT HEALTH]")
    if drift:
        print(f"  Spec drift ({len(drift)}):  {[d['tool'] for d in drift]}")
    else:
        print(f"  Spec drift:        none" + (" (validation not run)" if not meta["validated"] else ""))
    if unannotated:
        print(f"  Unannotated tools: {unannotated}")
    else:
        print(f"  DQ coverage:       100% — all active tools annotated")

    if meta["validated"]:
        print(f"\n[VALIDATION]")
        print(f"  Ran at:    {val.get('last_run', 'unknown')}")
        print(f"  Contracts: {val.get('contracts_passed', 0)}/{val.get('contracts_total', 0)} passed")
        print(f"  Drift:     {val.get('spec_drift_count', 0)} tools")

    print(f"\n{'='*60}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_spec_memory — unified spec-driven memory for the vault standard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_spec_memory.py                     # genera spec-memory.json
  python vault_spec_memory.py --check             # muestra sin escribir
  python vault_spec_memory.py --validate          # corre tests + actualiza test_status
  python vault_spec_memory.py --tool vault_write  # muestra spec de una tool
  python vault_spec_memory.py --summary           # dashboard legible por humano
  python vault_spec_memory.py --validate --summary  # validar + mostrar dashboard
""",
    )
    parser.add_argument("--check",    action="store_true", help="Mostrar spec-memory sin escribir")
    parser.add_argument("--validate", action="store_true", help="Correr tests y actualizar test_status")
    parser.add_argument("--summary",  action="store_true", help="Mostrar dashboard legible")
    parser.add_argument("--tool",     help="Mostrar spec de una tool específica")

    args = parser.parse_args()

    doc = build_spec_memory(validate=args.validate)

    if args.tool:
        entry = doc["tools"].get(args.tool)
        if not entry:
            print(json.dumps({"ok": False, "error": f"Tool not found: {args.tool}"}, indent=2))
            return 1
        print(json.dumps({"ok": True, "tool": args.tool, "spec": entry}, indent=2, ensure_ascii=False))
        return 0

    if args.summary:
        _print_summary(doc)
        if not args.check and not args.tool:
            _system_dir().mkdir(parents=True, exist_ok=True)
            _spec_memory_file().write_text(
                json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(json.dumps({"ok": True, "path": "00_System/spec-memory.json",
                               "tools": doc["surface"]["total"],
                               "active": doc["surface"]["active"]}, indent=2))
        return 0

    if args.check:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
        return 0

    _system_dir().mkdir(parents=True, exist_ok=True)
    _spec_memory_file().write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "ok": True,
        "path": "00_System/spec-memory.json",
        "standard_version": doc["meta"]["standard_version"],
        "tools": doc["surface"]["total"],
        "active": doc["surface"]["active"],
        "dq_coverage_pct": doc["surface"]["coverage_pct"],
        "fundamentals": len(doc["spec"]["fundamentals"]),
        "validated": doc["meta"]["validated"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_spec_memory"))
