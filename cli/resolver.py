"""Resolución única de operaciones instaladas y fallback de checkout."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class OperationTarget:
    kind: str
    module: Optional[str] = None
    path: Optional[Path] = None


def resolve_operation(fragment, *, legacy_scripts: Optional[Path] = None) -> OperationTarget:
    """Prefiere el módulo declarado; el fichero solo es fallback explícito."""
    module = getattr(fragment, "execution_module", None)
    if module:
        try:
            spec = importlib.util.find_spec(module)
        except (ImportError, AttributeError, ValueError):
            spec = None
        if spec is not None:
            return OperationTarget("installed", module=module)

    if legacy_scripts is not None:
        script = legacy_scripts / fragment.script
        if script.is_file():
            return OperationTarget("legacy", path=script)
    return OperationTarget("missing", module=module)
