"""Carga primaria instalada y compatibilidad aislada con checkout histórico."""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator, Optional


def legacy_scripts_for(anchor: str | Path) -> Optional[Path]:
    """Localiza ``scripts/`` solo para compatibilidad con un source checkout."""
    path = Path(anchor).resolve()
    for parent in path.parents:
        candidate = parent / "scripts"
        if (candidate / "vault_mcp_catalog.py").is_file() and (parent / ".git").exists():
            return candidate
    return None


@contextmanager
def _legacy_path(path: Path) -> Iterator[None]:
    """Expone temporalmente el layout antiguo; nunca queda en ``sys.path``."""
    value = str(path)
    already = value in sys.path
    if not already:
        sys.path.insert(0, value)
    try:
        yield
    finally:
        if not already:
            try:
                sys.path.remove(value)
            except ValueError:
                pass


def import_toolkit_module(name: str, *, legacy_scripts: Optional[Path] = None) -> ModuleType:
    """Importa primero la unidad instalada; el checkout es fallback explícito."""
    try:
        return importlib.import_module(name)
    except ImportError as installed_error:
        if legacy_scripts is None:
            raise
        candidate = legacy_scripts / f"{name}.py"
        if not candidate.is_file():
            raise installed_error
        with _legacy_path(legacy_scripts):
            return importlib.import_module(name)
