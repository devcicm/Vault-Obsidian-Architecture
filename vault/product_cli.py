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
from pathlib import Path
from typing import Any, Sequence

from .kernel.errores import construir_error
from .kernel import proyectos as _proyectos
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


#: Qué hacer con la CLI instalada según por qué no se ejecutó la tool. Sin
#: esto salía la pista del catálogo, «Ejecutar el script con --help», que no
#: tiene sentido sin checkout y no distinguía los casos (v40.34).
_PISTAS_DE_RESOLUCION = {
    UNKNOWN_TOOL: "`vault tools list` muestra las tools de esta instalación.",
    KNOWN_NOT_INSTALLED: (
        "La tool está catalogada pero esta instalación no la trae; "
        "`vault tools list` marca cuáles están instaladas."
    ),
    NOT_RUNTIME_OPERATION: (
        "Es mantenimiento del estándar, no operación sobre un vault: se ejecuta "
        "desde un checkout del repositorio (python scripts/<tool>.py), no desde "
        "la instalación."
    ),
    INVALID_INSTALLED_TARGET: (
        "La instalación está incompleta: reinstala el paquete y comprueba con "
        "`vault tools list`."
    ),
}


#: Código del catálogo y pista para cada fallo de init, doctor y status. Hasta
#: 2026-10-01 todos salían como INVALID_ACTION con la pista de `--help`: una
#: ruta mala y un runtime dañado eran indistinguibles para el consumidor.
_CICLO_DE_VIDA = {
    "INIT_INVALID_TARGET": (
        "INVALID_PATH",
        "Indica un directorio vacío o inexistente cuyo padre exista: "
        "`vault init` no crea directorios intermedios.",
    ),
    "INIT_CONFLICT": (
        "INVALID_PATH",
        "El directorio tiene contenido y no es un runtime: `vault init` nunca "
        "mezcla el seed con datos ajenos. Usa un directorio vacío.",
    ),
    "INIT_FAILED": (
        "UNEXPECTED_ERROR",
        "No quedó nada a medias; el detalle está en `message`. Comprueba "
        "permisos y espacio en el directorio padre.",
    ),
    "RUNTIME_MISSING": (
        "VAULT_NOT_FOUND",
        "Crea el runtime con `vault init <ruta>` o indica uno existente.",
    ),
    "NOT_RUNTIME": (
        "VAULT_NOT_FOUND",
        "La ruta no es un directorio: indica la raíz de un runtime.",
    ),
    "STANDARD_VERSION_MISSING": (
        "VERSION_READ_ERROR",
        "Falta 00_System/standard-version.json: el directorio no es un runtime "
        "creado por `vault init`, o se borró ese fichero.",
    ),
    "STANDARD_VERSION_INVALID": (
        "VERSION_READ_ERROR",
        "00_System/standard-version.json no se puede leer; el detalle está en "
        "`message`.",
    ),
    "SYSTEM_FILES_MISSING": (
        "FOLDER_NOT_FOUND",
        "Faltan las rutas de `missing`; vault_standard_upgrade --check las "
        "detecta y migra.",
    ),
    "MCP_PROJECT_WITHOUT_ROOT": (
        "MISSING_REQUIRED_ARG",
        "`--project` se resuelve contra el registro del vault: pasa `--root "
        "<vault>` o define VAULT_ROOT con una carpeta que exista.",
    ),
    "STANDARD_INCOMPATIBLE": (
        "VERSION_NOT_FOUND",
        "El runtime es de otra versión del estándar: si es más nueva, actualiza "
        "el paquete; si es más vieja, vault_standard_upgrade --check da la ruta.",
    ),
}


def _error(state: str, detail: str, exit_code: int) -> int:
    code, pista = _CICLO_DE_VIDA.get(
        state, ("INVALID_ACTION", _PISTAS_DE_RESOLUCION.get(state)))
    _emit(
        construir_error(
            "vault",
            code,
            detail,
            extra={"state": state, "error": detail},
            pista=pista,
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
            # La pista del catálogo ofrece `--force`, que es de `cli/vault_cli.py`.
            # Aquí no existe: se pasaría a la tool y el pre-flight rechazaría igual.
            pista=(
                "Revisar `findings`: cada hallazgo dice qué campo y por qué. "
                "Ninguna escritura ocurrió. Corregir el argumento señalado; "
                "`vault run` no ofrece forma de saltarse estas guardas."
            ),
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


def _poblar_con_vault_init(root: Path) -> dict[str, Any]:
    """Ejecuta el `vault_init` instalado sobre el runtime recién creado.

    Es lo mismo que haría `vault run vault_init` con `VAULT_ROOT` apuntando al
    runtime: índices de sección, hub con enlaces, nota de comandos y primers.
    Su salida JSON se recoge y no se reemite: el envelope de `vault init` es uno.
    """
    resolucion = resolver_producto("vault_init")
    if resolucion.estado != INSTALLED or resolucion.module is None:
        return {"ok": False, "detail": resolucion.detail or resolucion.estado}
    env = dict(os.environ, VAULT_ROOT=str(root), VAULT_STRICT_ROOT="1")
    proceso = subprocess.run(
        [sys.executable, "-m", resolucion.module, "--no-audit"],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proceso.returncode != 0:
        return {"ok": False, "detail": (proceso.stderr or proceso.stdout)[-500:],
                "hint": f"Reintentar con VAULT_ROOT={root} vault run vault_init"}
    return {"ok": True, "tool": "vault_init"}


def cmd_init(args: argparse.Namespace) -> int:
    return _lifecycle_result(
        inicializar_runtime(args.runtime, bootstrap=_poblar_con_vault_init)
    )


def cmd_doctor(args: argparse.Namespace) -> int:
    return _lifecycle_result(diagnosticar_runtime(args.runtime))


def cmd_status(args: argparse.Namespace) -> int:
    return _lifecycle_result(estado_runtime(args.runtime))


def _servidor_mcp() -> Path | None:
    """El `.mjs` instalado (`vault_toolkit/mcp/`) o, en el checkout, el del repo."""
    import vault_toolkit

    candidatos = (
        Path(vault_toolkit.__file__).resolve().parent / "mcp",
        Path(__file__).resolve().parent.parent / "mcp" / "nodejs",
    )
    for carpeta in candidatos:
        servidor = carpeta / "vault-mcp-server.mjs"
        if servidor.is_file():
            return servidor
    return None


#: `--root` y `--project` de `mcp-path`, leídos antes del parse: la fábrica de
#: `--project` resuelve durante el parse y `--root` puede venir detrás en el
#: argv; el nombre crudo hace falta para `project_resolved_from`.
_PREVIO: dict[str, str] = {}


def _raiz_pedida(root: str | None) -> str:
    return root or os.environ.get("VAULT_ROOT") or ""


def _raiz_de_mcp_path() -> Path:
    """Raíz contra la que se resuelve `mcp-path --project`, o fallo explícito.

    Sin vault, la fábrica resolvería contra el CWD y diría `PROJECT_NOT_FOUND`
    de un proyecto que quizá existe: el error tiene que nombrar lo que falta.
    """
    raiz = _raiz_pedida(_PREVIO.get("root"))
    if not raiz or not Path(raiz).is_dir():
        raise SystemExit(_error(
            "MCP_PROJECT_WITHOUT_ROOT",
            "--project necesita el vault (--root o VAULT_ROOT) para resolverse", 1))
    return Path(raiz)


def cmd_mcp_path(args: argparse.Namespace) -> int:
    """Ruta del servidor MCP y la entrada de configuración de un cliente.

    `VAULT_MCP_PYTHON` va fijada a este intérprete: el primer Python del PATH
    no tiene por qué ser el del venv donde se instaló el toolkit.

    Con `--project` (AP-63, P5) la configuración ata la sesión a ese proyecto:
    `VAULT_PROJECT` con el slug **ya resuelto aquí**, contra el registro del
    vault, y `VAULT_PROJECT_LOCK=1`. El servidor no resuelve nombres: copia el
    entorno a cada tool, y la fábrica de `--project` aplica el candado. El
    `--project` de este comando lo resuelve la misma fábrica que el de las 43
    tools (`_raiz_de_mcp_path`), así que llega aquí siendo ya el slug.
    """
    servidor = _servidor_mcp()
    if servidor is None:
        return _error("mcp_server_missing", "el servidor MCP no está en esta instalación", 1)
    raiz = _raiz_pedida(args.root)
    env: dict[str, str] = {
        "VAULT_ROOT": str(Path(raiz).resolve()) if raiz else "<ruta absoluta del vault>",
        "VAULT_MCP_PYTHON": sys.executable,
    }
    payload: dict[str, Any] = {"ok": True, "server": str(servidor), "python": sys.executable}
    if args.project:
        slug, pedido = args.project, _PREVIO.get("project") or args.project
        env[_proyectos.ENTORNO_PROYECTO] = slug
        env[_proyectos.ENTORNO_CANDADO] = "1"
        payload["project"] = slug
        payload["project_resolved_from"] = _proyectos.resuelto_desde(pedido, slug)
    payload["config"] = {"command": "node", "args": [str(servidor)], "env": env}
    _emit(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vault", allow_abbrev=False)
    parser.add_argument("--version", action="version", version=toolkit_version())
    commands = parser.add_subparsers(dest="command", required=True)

    tools = commands.add_parser("tools", help="Descubre tools del toolkit instalado", allow_abbrev=False)
    tool_commands = tools.add_subparsers(dest="tools_command", required=True)
    listing = tool_commands.add_parser("list", help="Lista tools declaradas", allow_abbrev=False)
    listing.set_defaults(func=cmd_tools_list)
    showing = tool_commands.add_parser("show", help="Muestra metadata derivada", allow_abbrev=False)
    showing.add_argument("tool")
    showing.set_defaults(func=cmd_tools_show)

    run = commands.add_parser("run", help="Ejecuta una operación instalada", allow_abbrev=False)
    run.add_argument("tool")
    run.add_argument("args", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)

    init = commands.add_parser("init", help="Crea un runtime externo nuevo", allow_abbrev=False)
    init.add_argument("runtime")
    init.set_defaults(func=cmd_init)
    doctor = commands.add_parser("doctor", help="Diagnostica un runtime sin escribir", allow_abbrev=False)
    doctor.add_argument("runtime")
    doctor.set_defaults(func=cmd_doctor)
    status = commands.add_parser("status", help="Muestra el estado read-only de un runtime", allow_abbrev=False)
    status.add_argument("runtime")
    status.set_defaults(func=cmd_status)
    mcp_path = commands.add_parser("mcp-path", help="Ruta del servidor MCP y su configuración de cliente", allow_abbrev=False)
    mcp_path.add_argument("--root", help="Vault que servirá el MCP (por defecto, VAULT_ROOT)")
    mcp_path.add_argument("--project", type=_proyectos.proyecto_registrado("vault", _raiz_de_mcp_path), help="Ata la sesión MCP a este proyecto (slug o alias registrado)")
    mcp_path.set_defaults(func=cmd_mcp_path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # El contrato es JSON en UTF-8, no en la codificación de la consola: con
    # stdout redirigido en Windows salía cp1252 y el consumidor recibía bytes
    # inválidos dentro del envelope (v40.34).
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    previo = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    previo.add_argument("--root")
    _PREVIO["root"] = previo.parse_known_args(argv)[0].root or ""
    # El nombre crudo, sin un segundo `add_argument("--project")`: ese solo
    # existe con la fábrica (AP-63), y aquí no se resuelve nada.
    crudo = list(sys.argv[1:] if argv is None else argv)
    for i, arg in enumerate(crudo):
        if arg == "--project" and i + 1 < len(crudo):
            _PREVIO["project"] = crudo[i + 1]
        elif arg.startswith("--project="):
            _PREVIO["project"] = arg.split("=", 1)[1]
    args = build_parser().parse_args(argv)
    return int(args.func(args))


# `python -m vault.product_cli` terminaba con rc=0 sin hacer nada: el módulo
# solo definía `main`. Un éxito sin trabajo es AP-37; `python -m vault` sigue
# siendo la forma documentada.
if __name__ == "__main__":
    sys.exit(main())
