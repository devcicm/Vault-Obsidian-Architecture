"""Política de resolución para el producto instalado.

No reutiliza el fallback de desarrollo: una tool conocida sin implementación
instalada debe explicarse al consumidor, no intentar encontrar ``scripts/``.
"""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from .catalogo_producto import ToolProducto, obtener_tool


INSTALLED = "installed"
KNOWN_NOT_INSTALLED = "known_not_installed"
NOT_RUNTIME_OPERATION = "not_runtime_operation"
UNKNOWN_TOOL = "unknown_tool"
INVALID_INSTALLED_TARGET = "invalid_installed_target"


@dataclass(frozen=True)
class ResolucionProducto:
    estado: str
    tool: ToolProducto | None = None
    module: str | None = None
    detail: str | None = None


def _imports_scripts(source: Path) -> bool:
    """Guard estático: no sustituye la prueba E2E de instalación limpia."""
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = (node.module,)
        else:
            continue
        if any(name == "scripts" or name.startswith("scripts.") for name in names):
            return True
    return False


def resolver_producto(nombre: str) -> ResolucionProducto:
    """Resuelve sólo destinos declarados instalables; jamás usa legacy."""
    tool = obtener_tool(nombre)
    if tool is None:
        return ResolucionProducto(UNKNOWN_TOOL, detail=f"tool desconocida: {nombre}")
    if tool.clase != "runtime":
        return ResolucionProducto(NOT_RUNTIME_OPERATION, tool=tool,
                                  detail=f"{nombre} es mantenimiento del estándar")
    if tool.execution_module is None:
        return ResolucionProducto(KNOWN_NOT_INSTALLED, tool=tool,
                                  detail=f"{nombre} aún no está instalada")
    try:
        spec = importlib.util.find_spec(tool.execution_module)
    except (ImportError, AttributeError, ValueError, ModuleNotFoundError) as exc:
        return ResolucionProducto(INVALID_INSTALLED_TARGET, tool=tool,
                                  detail=f"módulo no resoluble: {exc}")
    if spec is None or spec.origin in (None, "built-in", "frozen"):
        return ResolucionProducto(INVALID_INSTALLED_TARGET, tool=tool,
                                  detail="módulo instalado no resoluble")
    origin = Path(spec.origin).resolve()
    if any(part == "scripts" for part in origin.parts) or _imports_scripts(origin):
        return ResolucionProducto(INVALID_INSTALLED_TARGET, tool=tool,
                                  detail="el destino instalado depende de scripts/")
    return ResolucionProducto(INSTALLED, tool=tool, module=tool.execution_module)
