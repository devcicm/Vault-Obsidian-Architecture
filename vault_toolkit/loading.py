"""Carga primaria instalada y compatibilidad aislada con checkout histórico."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional


def legacy_scripts_for(anchor: str | Path) -> Optional[Path]:
    """Localiza ``scripts/`` solo para compatibilidad con un source checkout."""
    path = Path(anchor).resolve()
    for parent in path.parents:
        candidate = parent / "scripts"
        if (candidate / "vault_mcp_catalog.py").is_file() and (parent / ".git").exists():
            return candidate
    return None


def _asegurar_primero(path: str) -> None:
    """Añade path a sys.path[0] de forma persistente e idempotente."""
    if path not in sys.path:
        sys.path.insert(0, path)
    elif sys.path[0] != path:
        sys.path.remove(path)
        sys.path.insert(0, path)


def import_toolkit_module(name: str, *, legacy_scripts: Optional[Path] = None) -> ModuleType:
    """Importa primero _impl; legacy_scripts es fallback; después el installed."""
    impl_dir = Path(__file__).resolve().parent / "_impl"
    impl_path = str(impl_dir.resolve())
    if (impl_dir / f"{name}.py").is_file():
        _asegurar_primero(impl_path)
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            raise ImportError(
                f"vault_toolkit.operations.{name} no disponible en _impl (wheel instalada "
                f"puede estar corrupta): {exc}"
            ) from exc

    if legacy_scripts is not None:
        scripts_path = str(legacy_scripts.resolve())
        candidate = legacy_scripts / f"{name}.py"
        if candidate.is_file():
            _asegurar_primero(scripts_path)
            try:
                return importlib.import_module(name)
            except ImportError as exc:
                raise ImportError(
                    f"vault_toolkit.operations.{name} no disponible en legacy_scripts "
                    f"(checkout puede estar incompleto): {exc}"
                ) from exc

    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ImportError(
            f"vault_toolkit.operations.{name} no encontrado en "
            f"_impl ni en installed: {exc}"
        ) from exc
