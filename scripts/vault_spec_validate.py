#!/usr/bin/env python3
"""
vault_spec_validate.py — Valida que las implementaciones cumplan tool-spec.json.

Spec-driven: la spec en tool-spec.json es la fuente de verdad formal.
La implementación debe conformarse a lo declarado. Si hay drift → exit 1 (CI gate).

Checks por tool:
  1. script_exists   — scripts/{name}.py debe existir
  2. args_match      — required_args del spec deben estar en argparse del script
  3. returns_match   — SUPERSEDED por `vault_smoke.contract_gap` (2026-10-16).
                       Solo con `--returns-estatico`: claves de declared_returns
                       escritas como literal en un return{} (AST).
  4. folder_ownership — FOLDER del script coincide con vault_registry

`returns_match` medía con su propia normalización (AP-44): no ve `r["k"] = …`,
`r.update(...)` ni lo que pone un ayudante común (`write_report`, `emit_error`),
y daba drift a 90 de 145 tools. Ampliar el AST a subíndices y `update` se midió
y bajó de 98 a 95: el grueso lo ponen ayudantes de otro módulo. El criterio del
consumidor es el envelope emitido, y eso ya lo mide `vault_smoke` ejecutando el
ejemplo documentado de cada tool. El chequeo no se borra (no-derogación): sigue
detrás de `--returns-estatico` y el informe lo publica en `superseded_checks`.

Tampoco es «missing» lo que no vive en `scripts/` por diseño: las tools
archivadas (su `superseded_by` está en el spec), las JS nativas
(`NATIVE_JS_TOOLS`) y las que el catálogo ejecuta como `execution_module`.

Flujo correcto:
  1. Editar tool-spec.json (declarar spec ANTES de implementar)
  2. Implementar el script
  3. python vault_spec_validate.py --tool <name>  ← verificar conformidad
  4. Si hay drift → corregir implementación o actualizar spec con justificación

Usage:
    python vault_spec_validate.py                     # valida todas las tools
    python vault_spec_validate.py --tool vault_write  # valida una sola tool
    python vault_spec_validate.py --report            # human-readable
    python vault_spec_validate.py --strict            # falla también en scripts sin spec
    python vault_spec_validate.py --returns-estatico  # reactiva returns_match (superseded)
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import emit_error, wrap_main
from vault_io import resolve_tool_spec, tool_spec_path
from vault_registry import folder_owner, check_folder_collisions
from vault_mcp_catalog import NATIVE_JS_TOOLS, TOOLS_CATALOG
import vault_grafo_import

SCRIPTS_DIR = Path(__file__).parent

# Scripts que no son tools de usuario y se excluyen del check "unspecced"
_NON_TOOL_SCRIPTS = {
    "vault_errors", "vault_io", "vault_norms", "vault_test_runner",
    "vault_compact_contracts", "vault_manifest", "vault_spec_validate",
    "vault_spec_memory",
}


#: Chequeos retirados que siguen existiendo detrás de un flag. Se publican en
#: cada informe para que un verde no se lea como «returns_match pasó».
SUPERSEDED_CHECKS: Dict[str, Dict[str, str]] = {
    "returns_match": {
        "superseded_by": "vault_smoke.contract_gap",
        "since": "2026-10-16",
        "flag": "--returns-estatico",
        "why": (
            "AP-44: el AST solo ve claves escritas como literal en un return{}; "
            "daba drift a 90 de 145 tools y ampliarlo bajó de 98 a 95. "
            "vault_smoke contrasta el envelope que la tool emite de verdad."
        ),
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Spec loader
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


def load_spec() -> Dict[str, Any]:
    spec_file = resolve_tool_spec()
    if spec_file is None:
        raise FileNotFoundError(
            f"tool-spec.json no encontrado en {tool_spec_path()}\n"
            "Genera el spec inicial: python vault_manifest.py --bootstrap"
        )
    try:
        return json.loads(spec_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"tool-spec.json tiene JSON inválido: {e}") from e


# ──────────────────────────────────────────────────────────────────────────────
# Static analysis helpers
# ──────────────────────────────────────────────────────────────────────────────

def _read_source(name: str) -> Optional[str]:
    # Deuda #12: `scripts/<name>.py` puede ser un alias sin código; la fuente
    # es la del dueño (AP-44). Sin alias, `fuente_de` devuelve `scripts/<name>.py`.
    path = vault_grafo_import.fuente_de(name)
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        emit_error("vault_spec_validate", "SOURCE_READ_ERROR", str(exc))
        return None


def _fuente_de_modulo(name: str) -> Optional[str]:
    """Fuente de una tool que el catálogo ejecuta como módulo (`execution_module`).

    `vault_gobernanza` vive en `vault/gobernanza/tool.py` y no tiene
    `scripts/<name>.py`: leer solo `scripts/` la daba por ausente (AP-44).
    """
    modulo = (TOOLS_CATALOG.get(name) or {}).get("execution_module")
    if not modulo:
        return None
    path = vault_grafo_import.DIRECTORIO.parent / (modulo.replace(".", "/") + ".py")
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    except OSError as exc:
        emit_error("vault_spec_validate", "SOURCE_READ_ERROR", str(exc))
        return None


def _extract_argparse_flags(source: str) -> Set[str]:
    """Extrae todos los --flag declarados en add_argument()."""
    flags: Set[str] = set()
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
            for n in re.findall(r"""add_argument\(\s*["']([^"']+)["']""", call):
                if n.startswith("-"):
                    flags.add(n)
        i += 1
    return flags


def _extract_return_keys(source: str) -> Set[str]:
    """
    Análisis estático: claves string en dicts que son retornados por la función.

    Cubre tres patrones comunes en vault tools:
      1. return {"key": val, ...}               — dict inline en return
      2. result = {"key": val, ...}; return result — asignación + return de variable
      3. Cualquier dict que contenga "ok" como clave — señal de response object
    """
    keys: Set[str] = set()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None

    if tree is not None:
        # Paso 1: return {dict literal} directo
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)

        # Paso 2: varname = {dict}  →  return varname
        # Recopilar qué variables se retornan
        returned_vars: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
                returned_vars.add(node.value.id)

        # Recopilar dicts asignados a esas variables
        if returned_vars:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in returned_vars:
                            if isinstance(node.value, ast.Dict):
                                for k in node.value.keys:
                                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                        keys.add(k.value)
                elif isinstance(node, ast.AnnAssign):
                    # result: Dict[...] = {...}
                    if isinstance(node.target, ast.Name) and node.target.id in returned_vars:
                        if node.value and isinstance(node.value, ast.Dict):
                            for k in node.value.keys:
                                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                    keys.add(k.value)

    # Paso 3: regex fallback — dicts con "ok" como clave (response objects)
    for m in re.finditer(r'\{([^}]{0,800})\}', source, re.DOTALL):
        body = m.group(1)
        if '"ok"' in body or "'ok'" in body:
            for km in re.finditer(r'["\'](\w+)["\']\s*:', body):
                keys.add(km.group(1))

    return keys


def _extract_error_codes(source: str) -> Set[str]:
    codes: Set[str] = set()
    for m in re.finditer(r'"error_code"\s*:\s*"([^"]+)"', source):
        codes.add(m.group(1))
    for m in re.finditer(r"'error_code'\s*:\s*'([^']+)'", source):
        codes.add(m.group(1))
    return codes


# ──────────────────────────────────────────────────────────────────────────────
# Validation logic
# ──────────────────────────────────────────────────────────────────────────────

def validate_tool(name: str, spec_entry: Dict[str, Any],
                  returns_estatico: bool = False) -> Dict[str, Any]:
    """Valida una tool contra su entrada en el spec. Retorna resultado con drifts.

    `returns_estatico` reactiva `returns_match`, superseded por
    `vault_smoke.contract_gap` (ver `SUPERSEDED_CHECKS`).
    """
    result: Dict[str, Any] = {"tool": name, "status": "pass", "drifts": []}

    if spec_entry.get("status") == "archived":
        # Archivada: su código ya no existe y el spec dice quién la sustituye.
        result["status"] = "archived"
        result["superseded_by"] = spec_entry.get("superseded_by") or spec_entry.get("replaced_by")
        return result
    if name in NATIVE_JS_TOOLS:
        # Backend nativo en Node: no hay script Python que validar (AP-48).
        result["status"] = "js_native"
        return result

    source = _read_source(name)
    if source is None:
        source = _fuente_de_modulo(name)

    # Check 1: script_exists
    if source is None:
        result["status"] = "missing"
        result["drifts"].append({
            "check": "script_exists",
            "detail": f"scripts/{name}.py no encontrado",
        })
        return result

    # Check 2: required_args declarados en spec → deben estar en argparse
    spec_required: List[str] = spec_entry.get("required_args", [])
    if spec_required:
        impl_flags = _extract_argparse_flags(source)
        missing_args = [a for a in spec_required if a not in impl_flags]
        if missing_args:
            result["drifts"].append({
                "check": "args_match",
                "missing_in_impl": missing_args,
                "detail": f"En spec pero no en script: {missing_args}",
            })

    # Check 3: declared_returns → deben aparecer en al menos un return{} del script
    spec_returns: List[str] = spec_entry.get("declared_returns", [])
    checkable = [k for k in spec_returns if k != "ok"]  # "ok" siempre presente
    if checkable and returns_estatico:
        impl_keys = _extract_return_keys(source)
        missing_returns = [k for k in checkable if k not in impl_keys]
        if missing_returns:
            result["drifts"].append({
                "check": "returns_match",
                "missing_in_impl": missing_returns,
                "detail": f"En spec pero no encontrado en return{{}} del script: {missing_returns}",
            })

    # Check 4: folder_ownership — FOLDER constante del script debe coincidir con registry
    folder_match = re.search(r'^FOLDER\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if folder_match:
        impl_folder = folder_match.group(1)
        registry_owner = folder_owner(impl_folder)
        if registry_owner is not None and registry_owner != name:
            result["drifts"].append({
                "check": "folder_ownership",
                "impl_folder": impl_folder,
                "registry_owner": registry_owner,
                "detail": (
                    f"'{name}' declara FOLDER='{impl_folder}' pero vault_registry "
                    f"registra a '{registry_owner}' como owner. "
                    f"Añadir subfolder exclusivo en vault_registry.SUBFOLDERS."
                ),
            })

    if result["drifts"]:
        result["status"] = "drift"

    return result


def run_validation(
    spec: Dict[str, Any],
    tool_filter: Optional[str] = None,
    strict: bool = False,
    returns_estatico: bool = False,
) -> Dict[str, Any]:
    tools = spec.get("tools", {})

    # Detectar scripts sin entrada en spec
    all_scripts = {
        p.stem for p in SCRIPTS_DIR.glob("vault_*.py")
        if p.stem not in _NON_TOOL_SCRIPTS
    }
    unspecced = sorted(all_scripts - set(tools.keys()))

    if tool_filter:
        tools = {k: v for k, v in tools.items() if k == tool_filter}
        if not tools:
            return {"ok": False, "error_code": "TOOL_NOT_IN_SPEC",
                    "detail": f"'{tool_filter}' no está en tool-spec.json"}

    results = [validate_tool(name, entry, returns_estatico)
               for name, entry in sorted(tools.items())]

    passed  = sum(1 for r in results if r["status"] == "pass")
    drifted = sum(1 for r in results if r["status"] == "drift")
    missing = sum(1 for r in results if r["status"] == "missing")
    archived = sum(1 for r in results if r["status"] == "archived")
    js_native = sum(1 for r in results if r["status"] == "js_native")

    overall_ok = drifted == 0 and missing == 0
    if strict and unspecced:
        overall_ok = False

    return {
        "ok": overall_ok,
        "spec_version": spec.get("version", "unknown"),
        "total": len(results),
        "passed": passed,
        "drifted": drifted,
        "missing": missing,
        "archived": archived,
        "js_native": js_native,
        "superseded_checks": ({} if returns_estatico else SUPERSEDED_CHECKS),
        "unspecced_count": len(unspecced),
        "unspecced_tools": unspecced,
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Human-readable report
# ──────────────────────────────────────────────────────────────────────────────

def _print_report(v: Dict[str, Any]) -> None:
    print(f"\n=== Vault Spec Validation ({v.get('spec_version', '?')}) ===")
    print(
        f"Total: {v['total']}  "
        f"Pass: {v['passed']}  "
        f"Drift: {v['drifted']}  "
        f"Missing: {v['missing']}  "
        f"Unspecced: {v.get('unspecced_count', 0)}"
    )
    print()

    for r in v.get("results", []):
        if r["status"] == "pass":
            print(f"  OK  {r['tool']}")
        elif r["status"] in ("archived", "js_native"):
            print(f"  --  {r['tool']} ({r['status']})")
        else:
            tag = "MISSING" if r["status"] == "missing" else "DRIFT  "
            print(f"  {tag} {r['tool']}")
            for d in r.get("drifts", []):
                print(f"         [{d['check']}] {d['detail']}")

    unspecced = v.get("unspecced_tools", [])
    if unspecced:
        print(f"\n  Scripts sin spec ({len(unspecced)}) — declarar en tool-spec.json:")
        for u in unspecced:
            print(f"    ?  {u}")

    for check, datos in v.get("superseded_checks", {}).items():
        print(f"\n  [{check}] superseded por {datos['superseded_by']} "
              f"(reactivar con {datos['flag']})")

    status = "PASS" if v["ok"] else "FAIL"
    print(f"\nResultado: {status}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_spec_validate — valida implementaciones contra tool-spec.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Flujo spec-driven:
  1. Editar tool-spec.json (spec PRIMERO, implementación después)
  2. Implementar scripts/{tool}.py
  3. python vault_spec_validate.py --tool <name>  ← conformidad
  4. Si hay drift → corregir impl o actualizar spec con justificación

Ejemplos:
  python vault_spec_validate.py                     # valida todas
  python vault_spec_validate.py --tool vault_write  # una tool
  python vault_spec_validate.py --report            # human-readable
  python vault_spec_validate.py --strict            # falla en unspecced también
""",
        allow_abbrev=False,
    )
    parser.add_argument("--tool",   help="Validar solo esta tool (nombre del script sin .py)")
    parser.add_argument("--report", action="store_true", help="Salida human-readable")
    parser.add_argument("--strict", action="store_true",
                        help="Falla si hay scripts sin entrada en spec (--unspecced)")
    parser.add_argument("--returns-estatico", action="store_true",
                        help="Reactiva returns_match (superseded por vault_smoke.contract_gap)")

    args = parser.parse_args()

    try:
        spec = load_spec()
    except (FileNotFoundError, ValueError) as e:
        print(json.dumps({"ok": False, "error_code": "SPEC_LOAD_ERROR", "detail": str(e)},
                         indent=2, ensure_ascii=False))
        return 1

    validation = run_validation(spec, tool_filter=args.tool, strict=args.strict,
                                returns_estatico=args.returns_estatico)

    if args.report:
        _print_report(validation)
    else:
        print(json.dumps(validation, indent=2, ensure_ascii=False))

    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_spec_validate"))
