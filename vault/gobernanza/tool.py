"""Tool de gobernanza MCP — expone GobernanzaMCP como tool instalable.

Este módulo proporciona una interfaz de tool para GobernanzaMCP, permitiendo que
el servidor MCP llame validación de gobernanza como una operación de tool.

Uso como tool:
    python -m vault.gobernanza.tool --content "..." --vault-root /path/to/vault

El servidor MCP puede llamar esta tool para obtener un informe detallado de
gobernanza que incluye secret scan, content gate, bracket balance, Mermaid
syntax, y más — más completo que el runGuardChain en JS.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from .mcp_gobernanza import GobernanzaMCP
from .base import ValidationResult

TOOL_NAME = "vault_gobernanza"


def _create_gobernanza(vault_root: str | None) -> GobernanzaMCP:
    """Crea una instancia de GobernanzaMCP con el catálogo y normas canónicos."""
    from vault.meta_toolkit.catalog_adapter import ToolsCatalogAdapter
    from vault.kernel.adaptadores import NormasDelCatalogo

    catalog = ToolsCatalogAdapter()
    norms = NormasDelCatalogo()
    return GobernanzaMCP(catalog, norms, vault_root=vault_root, trace_enabled=True)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Valida contenido contra las normas de gobernanza del MCP.",
    )
    parser.add_argument("--content", required=True, help="Contenido a validar")
    parser.add_argument("--folder", default="", help="Carpeta destino (para path-anchored links)")
    parser.add_argument("--vault-root", help="Ruta al vault")
    parser.add_argument("--format", default="json", choices=["json", "text"],
                        help="Formato de salida")
    parser.add_argument("--trace", action="store_true",
                        help="Incluir trace de validación")
    return parser


class _FakeFragment:
    """Fragmento fake para validar contenido sin tool en el catálogo."""
    def __init__(self, name: str):
        self.name = name
        self.group = "meta"
        self.purpose = "governance validation"
        self.execution_module = None
        self.guards: List[str] = []
        self.side_effects: List[str] = []
        self.required_args: List[str] = []
        self.status = "active"
        self.runtime = "python"


def main(argv: list[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    g = _create_gobernanza(args.vault_root)

    fragment = _FakeFragment(TOOL_NAME)
    check_args = {
        "content": args.content,
        "folder": args.folder,
    }

    result = g._pre_flight_specific(fragment, check_args)

    output: Dict[str, Any] = {
        "ok": result.ok,
        "tool": TOOL_NAME,
        "message": result.message,
        "findings": [
            {
                "rule": f.get("rule", "unknown"),
                "kind": f.get("kind", "unknown"),
                "message": f.get("message", str(f)),
            }
            for f in result.findings
        ],
    }

    if args.trace:
        output["trace"] = g.get_trace()

    if args.format == "text":
        if output["ok"]:
            print(f"OK: {output['message']}")
        else:
            print(f"FALLO: {output['message']}")
            for f in output["findings"]:
                print(f"  [{f['rule']}] {f['kind']}: {f['message']}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
