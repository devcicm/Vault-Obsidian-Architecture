"""Superficie pública mínima del toolkit instalado.

Esta CLI no es ``cli/``: sólo descubre la proyección empaquetada y ejecuta
operaciones con una promesa explícita ``execution_module``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib import metadata
from typing import Any, Sequence

from .kernel.errores import construir_error
from .meta_toolkit.catalogo_producto import catalogo_producto, obtener_tool
from .meta_toolkit.resolucion_producto import (
    INSTALLED,
    INVALID_INSTALLED_TARGET,
    KNOWN_NOT_INSTALLED,
    NOT_RUNTIME_OPERATION,
    UNKNOWN_TOOL,
    resolver_producto,
)


DIST_NAME = "vault-obsidian-architecture"
EXIT_UNKNOWN = 3
EXIT_NOT_INSTALLED = 4
EXIT_NOT_RUNTIME = 5
EXIT_INVALID_TARGET = 6
EXIT_OPERATION_FAILED = 7


def toolkit_version() -> str:
    """Versión de la distribución instalada, no del estándar de runtime."""
    return metadata.version(DIST_NAME)


def _emit(payload: dict[str, Any], *, stream: Any = None) -> None:
    target = stream or sys.stdout
    print(json.dumps(payload, ensure_ascii=False), file=target)


def _error(state: str, detail: str, exit_code: int) -> int:
    _emit(
        construir_error(
            "vault",
            "INVALID_ACTION",
            detail,
            extra={"state": state, "error": detail},
        ),
        stream=sys.stderr,
    )
    return exit_code


def cmd_tools_list(_: argparse.Namespace) -> int:
    tools = catalogo_producto()
    _emit({
        "ok": True,
        "tools": [
            {
                "name": tool.nombre,
                "class": tool.clase,
                "installed": tool.execution_module is not None,
            }
            for tool in tools.values()
        ],
    })
    return 0


def cmd_tools_show(args: argparse.Namespace) -> int:
    tool = obtener_tool(args.tool)
    if tool is None:
        return _error(UNKNOWN_TOOL, f"tool desconocida: {args.tool}", EXIT_UNKNOWN)
    _emit({
        "ok": True,
        "name": tool.nombre,
        "nature": tool.naturaleza,
        "class": tool.clase,
        "runtime_operation": tool.clase == "runtime",
        "distributable": tool.distributable,
        "installed": tool.execution_module is not None,
        "execution_module": tool.execution_module,
    })
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    result = resolver_producto(args.tool)
    if result.estado == UNKNOWN_TOOL:
        return _error(result.estado, result.detail or "tool desconocida", EXIT_UNKNOWN)
    if result.estado == KNOWN_NOT_INSTALLED:
        return _error(result.estado, result.detail or "tool no instalada", EXIT_NOT_INSTALLED)
    if result.estado == NOT_RUNTIME_OPERATION:
        return _error(result.estado, result.detail or "tool no runtime", EXIT_NOT_RUNTIME)
    if result.estado == INVALID_INSTALLED_TARGET:
        return _error(result.estado, result.detail or "destino inválido", EXIT_INVALID_TARGET)
    assert result.estado == INSTALLED and result.module is not None
    process = subprocess.run([sys.executable, "-m", result.module, *args.args])
    return 0 if process.returncode == 0 else EXIT_OPERATION_FAILED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vault")
    parser.add_argument("--version", action="version", version=toolkit_version())
    commands = parser.add_subparsers(dest="command", required=True)

    tools = commands.add_parser("tools", help="Descubre tools del toolkit instalado")
    tool_commands = tools.add_subparsers(dest="tools_command", required=True)
    listing = tool_commands.add_parser("list", help="Lista tools declaradas")
    listing.set_defaults(func=cmd_tools_list)
    showing = tool_commands.add_parser("show", help="Muestra metadata derivada")
    showing.add_argument("tool")
    showing.set_defaults(func=cmd_tools_show)

    run = commands.add_parser("run", help="Ejecuta una operación instalada")
    run.add_argument("tool")
    run.add_argument("args", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
