"""Proyección de distribución derivada de los registros canónicos.

No publica una segunda lista de tools ni presupone que exista ya un módulo
instalable por operación. Esa última frontera pertenece al siguiente paso de
PR5; mientras tanto ``execution_module`` declara honestamente ``None``.
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
    # La proyección actual no asigna operaciones instaladas. El tipo admite la
    # declaración futura para que el resolver pueda distinguir una ausencia
    # honesta de un destino explícito que deba verificarse.
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
        resultado[nombre] = DistribucionTool(
            nombre=nombre,
            naturaleza=naturaleza,
            clase="runtime" if es_runtime else "maintenance",
            distributable=es_runtime,
            legacy_script=catalogo[nombre].get("script"),
        )
    return resultado
