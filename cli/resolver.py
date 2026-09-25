"""Resuelve una operación declarada sin inventar una frontera instalada.

La proyección de distribución es la autoridad de la disponibilidad instalada.
Mientras una tool tenga ``execution_module=None``, el único destino ejecutable
es su adaptador histórico en ``scripts/``. Un módulo explícitamente declarado
se valida antes de usarlo: una fachada que vuelva a importar ``scripts`` no es
una operación instalada.
"""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OperationTarget:
    """Destino verificable de una ejecución de la CLI."""

    kind: str
    module: str | None = None
    path: Path | None = None
    detail: str | None = None


def _imports_scripts(source: Path) -> bool:
    """Detecta el wrapper que conserva una dependencia al adaptador legacy."""
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


def _installed_target(metadata: Any, *, legacy_scripts: Path | None) -> OperationTarget | None:
    """Verifica un destino instalado declarado, sin importarlo ni ejecutarlo."""
    module = metadata.execution_module
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, AttributeError, ValueError, ModuleNotFoundError) as exc:
        return OperationTarget("invalid", module=module,
                               detail=f"módulo instalado no resoluble: {exc}")
    if spec is None:
        return None
    _spec_origin = getattr(spec, 'origin', None)
    if _spec_origin in ("built-in", "frozen"):
        return OperationTarget("invalid", module=module,
                               detail="módulo instalado no resoluble")
    origin = Path(_spec_origin).resolve() if _spec_origin else None
    if legacy_scripts is not None and origin is not None:
        try:
            origin.relative_to(legacy_scripts.resolve())
        except ValueError:
            pass
        else:
            return OperationTarget("invalid", module=module,
                                   detail="el módulo instalado vive en scripts/")
    if origin is not None and _imports_scripts(origin):
        return OperationTarget("invalid", module=module,
                               detail="el módulo instalado importa scripts/")
    return OperationTarget("installed", module=module, path=origin)


def resolve_operation(fragment: Any, *, legacy_scripts: Path | None) -> OperationTarget:
    """Resuelve desde metadata canónica; script sólo si no hay destino instalado.

    Un ``execution_module`` explícito es una promesa de producto: si no se
    puede verificar, se informa como inválido en vez de degradarlo en silencio
    a una falsa operación instalada. Sin esa promesa, se conserva el adaptador
    legacy de checkout.
    """
    metadata = getattr(fragment, "distribution", None)
    module = getattr(metadata, "execution_module", None)
    if module is not None:
        result = _installed_target(metadata, legacy_scripts=legacy_scripts)
        if result is not None:
            return result

    script_name = getattr(fragment, "script", None)
    if legacy_scripts is not None and script_name:
        script = legacy_scripts / script_name
        if script.is_file():
            return OperationTarget("legacy", path=script)
    return OperationTarget("missing", detail="no hay operación instalada ni adaptador legacy")
