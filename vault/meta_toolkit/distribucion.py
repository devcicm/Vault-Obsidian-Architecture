"""Proyección de distribución derivada de los registros canónicos.

No publica una segunda lista de tools. ``execution_module`` sólo se proyecta
cuando el catálogo canónico declara una implementación estable ejecutable;
su ausencia sigue declarando honestamente que no hay operación instalada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DistribucionTool:
    """Lectura derivada de una tool, no metadata editorial nueva."""

    nombre: str
    naturaleza: str
    clase: str
    distributable: bool
    legacy_script: str | None
    # Sólo el catálogo canónico puede declarar este destino. El resolver
    # distingue una ausencia honesta de una promesa explícita a verificar.
    execution_module: str | None = None


def derivar_distribucion(
    catalogo: Mapping[str, Mapping[str, Any]],
    naturalezas: Mapping[str, Mapping[str, Any]],
) -> dict[str, DistribucionTool]:
    """Deriva la frontera runtime/meta y falla ante cualquier desacuerdo.

    ``TOOLS_CATALOG`` posee la existencia y el adaptador histórico; ``NATURALEZAS``
    posee si una tool actúa sobre un runtime o sobre este repositorio. Ninguno se
    duplica aquí. La ausencia de un módulo instalado es deliberada y verificable.
    """
    pertenencia = {nombre: [] for nombre in catalogo}
    for naturaleza, entrada in naturalezas.items():
        for nombre in entrada.get("tools", ()):
            if nombre in pertenencia:
                pertenencia[nombre].append(naturaleza)

    invalidas = {nombre: clases for nombre, clases in pertenencia.items() if len(clases) != 1}
    extras = sorted(
        nombre
        for entrada in naturalezas.values()
        for nombre in entrada.get("tools", ())
        if nombre not in catalogo
    )
    if invalidas or extras:
        raise ValueError(f"catálogo/naturalezas divergentes: invalidas={invalidas}, extras={extras}")

    resultado = {}
    for nombre in sorted(catalogo):
        naturaleza = pertenencia[nombre][0]
        es_runtime = naturaleza != "meta_estandar"
        execution_module = catalogo[nombre].get("execution_module")
        if execution_module is not None and (
            not isinstance(execution_module, str) or not execution_module.strip()
        ):
            raise ValueError(
                f"execution_module inválido para {nombre}: {execution_module!r}"
            )
        resultado[nombre] = DistribucionTool(
            nombre=nombre,
            naturaleza=naturaleza,
            clase="runtime" if es_runtime else "maintenance",
            distributable=es_runtime,
            legacy_script=catalogo[nombre].get("script"),
            execution_module=execution_module,
        )
    return resultado
