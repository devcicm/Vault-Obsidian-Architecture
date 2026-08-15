#!/usr/bin/env python3

"""
Vault Mermaid Check — Validación completa de diagramas Mermaid.

Detecta errores de sintaxis en bloques ```mermaid``` y proporciona
sugerencias de corrección. Soporta: flowchart, sequenceDiagram,
classDiagram, stateDiagram, erDiagram, gantt, pie.

Usage:
    python vault_mermaid_check.py
    python vault_mermaid_check.py --path "06_Diagrams/foo.md"
    python vault_mermaid_check.py --fix
    python vault_mermaid_check.py --project "mi-api"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import emit_error, wrap_main
from vault_io import is_snapshot_path
SCRIPTS_DIR = Path(__file__).parent


# superseded_by: vault_mermaid_reglas (v40.28) — AP-62. La gramática y sus
# validadores se fueron a una hoja del núcleo; aquí se reexportan para no
# derogar el contrato. Ver `vault_mermaid_reglas` para el porqué.
from vault_mermaid_reglas import MERMAID_TYPES  # noqa: F401,E402


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


# superseded_by: vault_mermaid_reglas (v40.28) — AP-62. Ver arriba.
from vault_mermaid_reglas import (  # noqa: F401,E402
    detect_mermaid_type,
    validate_class,
    validate_er,
    validate_flowchart,
    validate_gantt,
    validate_mermaid,
    validate_pie,
    validate_sequence,
    validate_state,
)


def check_file(path: Path) -> Dict[str, Any]:
    """Verifica un archivo por bloques Mermaid."""
    result = {
        "file": str(path),
        "valid": True,
        "blocks": [],
        "errors": [],
    }

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        result["valid"] = False
        result["errors"].append({"type": "read_error", "message": str(e)})
        return result

    pattern = r"```mermaid\s*\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    for idx, diagram in enumerate(matches):
        block_result = {
            "index": idx,
            "type": detect_mermaid_type(diagram),
            "valid": True,
            "errors": [],
        }

        todos = validate_mermaid(diagram)
        # Un aviso no invalida el diagrama. AP-25 penaliza -2 por cada entrada
        # de `errors`, así que mezclar avisos con errores de sintaxis convierte
        # una preferencia de estilo en una caída del health score.
        errors = [e for e in todos if e.get("severity") != "info"]
        avisos = [e for e in todos if e.get("severity") == "info"]
        if avisos:
            block_result["warnings"] = avisos
        if errors:
            block_result["valid"] = False
            block_result["errors"] = errors
            result["valid"] = False
            result["errors"].extend(errors)

        result["blocks"].append(block_result)

    return result


def scan_vault(
    path: Optional[Path] = None, project: Optional[str] = None
) -> Dict[str, Any]:
    """Escanea el vault por diagramas Mermaid."""
    search_root = path or _raiz()

    if project:
        search_root = _raiz() / "01_Projects" / project

    files_checked = 0
    results = []

    for md in search_root.rglob("*.md"):
        # `is_snapshot_path` sustituye al `".history" in str(md)` anterior, que
        # dejaba pasar `vault-backups/` y `.trash/`: 46 de los 69 errores AP-25
        # de BuilderX vivían en instantáneas congeladas. Peor con `--fix`, que
        # reescribía diagramas dentro de una copia de seguridad.
        # Relativo a la raíz del barrido: con la ruta absoluta, un directorio
        # ancestro FUERA del vault que se llamara `.trash` excluiría el vault
        # entero en silencio.
        try:
            rel_md = md.relative_to(search_root)
        except ValueError:  # pragma: no cover — rglob siempre cuelga de la raíz
            rel_md = md
        if is_snapshot_path(rel_md) or md.name.startswith("_"):
            continue
        files_checked += 1
        result = check_file(md)
        if result["blocks"]:
            results.append(result)

    total_errors = sum(len(r["errors"]) for r in results)
    all_valid = all(r["valid"] for r in results)

    return {
        "ok": all_valid,
        "files_checked": files_checked,
        "files_with_diagrams": len(results),
        "total_errors": total_errors,
        "results": results,
    }


def fix_common_issues(diagram: str) -> Tuple[str, List[str]]:
    """Intenta corregir errores comunes automáticamente."""
    fixes = []
    result = diagram

    result = re.sub(r"\{\s*\{", "{", result)
    result = re.sub(r"\}\s*\}", "}", result)
    if result != diagram:
        fixes.append("Colapsó llaves anidadas")

    result = re.sub(r"\[\s*\[", "[", result)
    result = re.sub(r"\]\s*\]", "]", result)
    if result != diagram:
        fixes.append("Colapsó corchetes anidados")

    return result, fixes


def main():
    parser = argparse.ArgumentParser(
        description="Vault Mermaid Check - Valida diagramas Mermaid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_mermaid_check.py
  python vault_mermaid_check.py --path "06_Diagrams/foo.md"
  python vault_mermaid_check.py --project "mi-api"
  python vault_mermaid_check.py --fix
  python vault_mermaid_check.py --path "06_Diagrams/foo.md" --fix
        """,
    )

    parser.add_argument("--path", type=str, help="Archivo específico a verificar")
    parser.add_argument("--project", type=str, help="Proyecto a verificar")
    parser.add_argument("--fix", action="store_true", help="Intentar auto-corrección")
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    if args.path:
        path = _raiz() / args.path
        if not path.exists():
            print(
                json.dumps(
                    emit_error("vault_mermaid_check", "FILE_NOT_FOUND", f"Archivo no encontrado: {args.path}"),
                    ensure_ascii=False,
                )
            )
            return 1
        result = check_file(path)
    elif args.project:
        result = scan_vault(project=args.project)
    else:
        result = scan_vault()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok", True):
            print(
                f"✓ Validación exitosa: {result.get('files_with_diagrams', 0)} diagramas revisados"
            )
            return 0
        else:
            print(f"✗ Errores encontrados: {result.get('total_errors', 0)}")
            for res in result.get("results", []):
                if not res["valid"]:
                    print(f"\nArchivo: {res['file']}")
                    for block in res.get("blocks", []):
                        if not block["valid"]:
                            for err in block.get("errors", []):
                                print(f"  - {err['type']}: {err['message']}")
                                if err.get("suggestion"):
                                    print(f"    Sugerencia: {err['suggestion']}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_mermaid_check"))
