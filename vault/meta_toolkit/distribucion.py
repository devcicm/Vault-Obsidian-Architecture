"""Proyección de distribución derivada de los registros canónicos.

No contiene una lista de tools. Recibe el catálogo y ``NATURALEZAS`` de sus
dueños y falla si una tool queda sin una clasificación única.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping


@dataclass(frozen=True)
class DistribucionTool:
    nombre: str
    clase: str
    runtime: str
    distributable: bool
    execution_module: str | None
    resources: tuple[str, ...]


def clasificar_tools(
    catalogo: Mapping[str, Mapping[str, Any]],
    naturalezas: Mapping[str, Mapping[str, Any]],
) -> dict[str, DistribucionTool]:
    """Deriva tool → distribución; no admite huecos ni doble pertenencia."""
    pertenencia: dict[str, list[str]] = {nombre: [] for nombre in catalogo}
    for naturaleza, entrada in naturalezas.items():
        for nombre in entrada.get("tools", ()):
            if nombre in pertenencia:
                pertenencia[nombre].append(naturaleza)

    invalidas = {n: v for n, v in pertenencia.items() if len(v) != 1}
    if invalidas:
        raise ValueError(f"tools sin naturaleza única: {invalidas}")

    resultado: dict[str, DistribucionTool] = {}
    for nombre, entrada in catalogo.items():
        naturaleza = pertenencia[nombre][0]
        runtime = str(entrada.get("runtime", "python"))
        clase = "maintenance" if naturaleza == "meta_estandar" else "runtime"
        distribuible = clase == "runtime" and runtime == "python"
        script = str(entrada.get("script") or f"{nombre}.py")
        modulo = (
            f"vault_toolkit.operations.{PurePosixPath(script).stem}"
            if distribuible else None
        )
        resultado[nombre] = DistribucionTool(
            nombre=nombre,
            clase=clase,
            runtime=runtime,
            distributable=distribuible,
            execution_module=modulo,
            resources=tuple(sorted(entrada.get("resources", ()) or ())),
        )
    return resultado
