"""Superficie pública mínima del toolkit instalado.

Esta CLI no es ``cli/``: sólo descubre la proyección empaquetada y ejecuta
operaciones con una promesa explícita ``execution_module``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from importlib import metadata
from typing import Any, Sequence

from .kernel.errores import construir_error
from .kernel.adaptadores import NormasDelCatalogo
from .ciclo_de_vida.producto import (
    inicializar_runtime,
    diagnosticar_runtime,
    estado_runtime,
)
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
EXIT_RUNTIME_INVALID = 8
EXIT_INIT_CONFLICT = 9
EXIT_PREFLIGHT_FAILED = 10

_RE_FLAG = re.compile(r"^--([a-zA-Z0-9_-]+)(?:=(.*))?$")


def _parse_args(args: list[str]) -> dict[str, Any]:
    """Convierte argumentos CLI estilo --key value --flag en dict."""
    result: dict[str, Any] = {}
    i = 0
    while i < len(args):
        arg = args[i]
        match = _RE_FLAG.match(arg)
        if not match:
            i += 1
            continue
        key = match.group(1).replace("-", "_")
        if match.group(2) is not None:
            result[key] = match.group(2)
            i += 1
        elif i + 1 < len(args) and not args[i + 1].startswith("--"):
            result[key] = args[i + 1]
            i += 2
        else:
            result[key] = True
            i += 1
    return result


def _gobernanza() -> Any:
    """Lazy import de GobernanzaCLI para evitar circular imports."""
    from .meta_toolkit.catalog_adapter import ToolsCatalogAdapter, NormCatalogAdapter

    vault_root = os.environ.get("VAULT_ROOT")
    tools_adapter = ToolsCatalogAdapter()
    norms_adapter = NormCatalogAdapter(NormasDelCatalogo())

    from .gobernanza import GobernanzaCLI
    return GobernanzaCLI(
        catalog=tools_adapter,
        norms=norms_adapter,
        vault_root=vault_root,
        verify_integrity=False,
    )


def toolkit_version() -> str:
    """Versión de la distribución instalada, no del estándar de runtime."""
    try:
        return metadata.version(DIST_NAME)
    except metadata.PackageNotFoundError:
        return "0.0.0.dev0+source"


def _emit(payload: dict[str, Any], *, stream: Any = None) -> None:
    target = stream or sys.stdout
    print(json.dumps(_sanitize_payload(payload), ensure_ascii=False), file=target)


def _sanitize_payload(obj: Any) -> Any:
    """Reemplaza caracteres nulos que rompen JSON serialization."""
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    if isinstance(obj, dict):
        return {k: _sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(item) for item in obj]
    return obj


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

    args_dict = _parse_args(args.args)
    g = _gobernanza()
    validation = g.pre_flight(args.tool, args_dict)
    if not validation.ok:
        error = construir_error(
            "vault",
            "PREFLIGHT_REJECTED",
            validation.message or "Pre-flight CLI encontró problemas",
            extra={
                "tool": args.tool,
                "phase": "pre-flight",
                "blocked": True,
                "findings": validation.findings,
            },
        )
        _emit(error, stream=sys.stderr)
        return EXIT_PREFLIGHT_FAILED

    assert result.estado == INSTALLED and result.module is not None
    process = subprocess.run([sys.executable, "-m", result.module, *args.args])
    return 0 if process.returncode == 0 else EXIT_OPERATION_FAILED


def _lifecycle_result(result: dict[str, Any]) -> int:
    if result.get("ok"):
        _emit(result)
        return 0
    state = str(result.get("state", "INVALID_RUNTIME"))
    detail = str(result.get("detail") or state)
    code = EXIT_INIT_CONFLICT if state == "INIT_CONFLICT" else EXIT_RUNTIME_INVALID
    return _error(state, detail, code)


def cmd_init(args: argparse.Namespace) -> int:
    return _lifecycle_result(inicializar_runtime(args.runtime))


def cmd_doctor(args: argparse.Namespace) -> int:
    return _lifecycle_result(diagnosticar_runtime(args.runtime))


def cmd_status(args: argparse.Namespace) -> int:
    return _lifecycle_result(estado_runtime(args.runtime))


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

    init = commands.add_parser("init", help="Crea un runtime externo nuevo")
    init.add_argument("runtime")
    init.set_defaults(func=cmd_init)
    doctor = commands.add_parser("doctor", help="Diagnostica un runtime sin escribir")
    doctor.add_argument("runtime")
    doctor.set_defaults(func=cmd_doctor)
    status = commands.add_parser("status", help="Muestra el estado read-only de un runtime")
    status.add_argument("runtime")
    status.set_defaults(func=cmd_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
