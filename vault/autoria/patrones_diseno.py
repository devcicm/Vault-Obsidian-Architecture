"""Reexportacion de `vault.kernel.patrones_diseno` para consumidores del contexto `autoria`."""

from __future__ import annotations

from vault.kernel.patrones_diseno import (  # noqa: F401
    CATALOGO_PATRONES,
    CATEGORIAS,
    ETIQUETAS_CATEGORIA,
    catalogo_ordenado,
    detectar_patrones,
    normalizar_nombre_patron,
)

__all__ = [
    "CATALOGO_PATRONES",
    "CATEGORIAS",
    "ETIQUETAS_CATEGORIA",
    "catalogo_ordenado",
    "detectar_patrones",
    "normalizar_nombre_patron",
]
