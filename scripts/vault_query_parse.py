#!/usr/bin/env python3
"""Adaptador legacy de ``vault.consulta.query_parse``.

El parser y la implementación viven en el paquete estable. Este script conserva
el nombre histórico, el contrato de ``vault_registry`` y el envelope CLI del
checkout, sin convertirse en dependencia de la operación instalada.
"""

from __future__ import annotations

import argparse
import json
import sys

from vault_errors import wrap_main
from vault_registry import standard_folders
from vault.consulta.query_parse import *  # noqa: F401,F403 - compatibilidad de imports
from vault.consulta.query_parse import vault_query_parse as _stable_query_parse


def vault_query_parse(query, now=None):
    """Compatibilidad histórica con el registro de secciones del checkout."""
    return _stable_query_parse(
        query, now=now, available_sections=list(standard_folders())
    )


def main() -> int:
    """Conserva el parser AP-40 y delega toda la semántica estable."""
    parser = argparse.ArgumentParser(
        description="vault_query_parse — lenguaje natural → consulta estructurada",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", default=None,
                        help="Pregunta en lenguaje natural")
    parser.add_argument("--query", dest="query_flag", default=None,
                        help="La misma pregunta, en forma nombrada (la que usa MCP)")
    parser.add_argument("--explain", action="store_true",
                        help="Muestra la evidencia de cada campo inferido")
    parser.add_argument("--plan-only", action="store_true",
                        help="Emite solo el plan de tools")
    args = parser.parse_args()
    pregunta = args.query_flag or args.query
    if not pregunta:
        parser.error("falta la pregunta: pasala como posicional o con --query")
    result = vault_query_parse(pregunta)
    if result.get("ok"):
        if args.plan_only:
            result = {"ok": True, "plan": result["plan"]}
        elif not args.explain:
            result.pop("evidence", None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_query_parse"))
