"""Lectura instalada del catálogo de producto derivado.

El JSON es producido por ``scripts/vault_mcp_catalog.py --sync`` desde el
catálogo canónico de desarrollo. Esta capa no conoce ``scripts/``: transporta
la clasificación necesaria para descubrir una tool desde un wheel instalado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Mapping

from .naturalezas import NATURALEZAS


@dataclass(frozen=True)
class ToolProducto:
    """Vista derivada y de sólo lectura de una tool instalada."""

    nombre: str
    proposito: str
    grupo: str
    naturaleza: str
    clase: str
    distributable: bool
    legacy_script: str | None
    execution_module: str | None


def _naturaleza_por_tool() -> dict[str, str]:
    salida: dict[str, str] = {}
    for naturaleza, entrada in NATURALEZAS.items():
        for nombre in entrada.get("tools", ()):
            if nombre in salida:
                raise ValueError(f"tool en dos naturalezas: {nombre}")
            salida[nombre] = naturaleza
    return salida


@lru_cache(maxsize=1)
def catalogo_producto() -> dict[str, ToolProducto]:
    """Carga el recurso distribuido y verifica su cobertura semántica."""
    resource = resources.files(__package__).joinpath("tools-catalog.json")
    raw: Mapping[str, Any] = json.loads(resource.read_text(encoding="utf-8"))
    tools = raw.get("tools")
    if not isinstance(tools, Mapping):
        raise ValueError("catálogo de producto inválido: falta tools")
    naturalezas = _naturaleza_por_tool()
    if set(tools) != set(naturalezas):
        raise ValueError("catálogo de producto/naturalezas divergentes")

    resultado: dict[str, ToolProducto] = {}
    for nombre, entry in tools.items():
        if not isinstance(entry, Mapping):
            raise ValueError(f"entrada de producto inválida: {nombre}")
        naturaleza = naturalezas[nombre]
        runtime = naturaleza != "meta_estandar"
        module = entry.get("execution_module")
        if module is not None and (not isinstance(module, str) or not module.strip()):
            raise ValueError(f"execution_module inválido para {nombre}: {module!r}")
        resultado[nombre] = ToolProducto(
            nombre=nombre,
            proposito=str(entry.get("description", "")),
            grupo=str(entry.get("group", "")),
            naturaleza=naturaleza,
            clase="runtime" if runtime else "maintenance",
            distributable=runtime,
            legacy_script=entry.get("script") or None,
            execution_module=module,
        )
    return dict(sorted(resultado.items()))


def obtener_tool(nombre: str) -> ToolProducto | None:
    return catalogo_producto().get(nombre)
