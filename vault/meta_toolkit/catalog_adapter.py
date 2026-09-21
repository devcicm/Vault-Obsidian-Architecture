"""Adaptadores de catálogo para la capa de gobernanza.

GobernanzaBase necesita acceder al catálogo de tools y al catálogo de normas
a través de protocolos definidos (ToolsCatalog, NormCatalog). Estos adaptadores
conectan los registros canónicos del toolkit con esos protocolos.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .catalogo_producto import ToolProducto, catalogo_producto


class ToolsCatalogAdapter:
    """Adapta ``catalogo_producto`` al protocolo ``ToolsCatalog`` de gobernanza.

    Lee el recurso ``tools-catalog.json`` instalado y expone una interfaz
    ``ToolsCatalog`` con ``por_nombre``, ``todas`` y ``por_grupo``.
    """

    def __init__(self) -> None:
        self._cache: Optional[Dict[str, ToolProducto]] = None

    def _load(self) -> Dict[str, ToolProducto]:
        if self._cache is None:
            self._cache = catalogo_producto()
        return self._cache

    def por_nombre(self, name: str) -> Optional["ToolFragment"]:
        producto = self._load().get(name)
        if producto is None:
            return None
        return self._to_fragment(producto)

    def todas(self) -> List["ToolFragment"]:
        return [self._to_fragment(p) for p in self._load().values()]

    def por_grupo(self, group: str) -> List["ToolFragment"]:
        return [
            self._to_fragment(p)
            for p in self._load().values()
            if p.grupo.lower() == group.lower()
        ]

    def _to_fragment(self, producto: ToolProducto) -> "ToolFragment":
        from ..gobernanza.base import ToolFragment
        return ToolFragment(
            name=producto.nombre,
            group=producto.grupo,
            purpose=producto.proposito,
            execution_module=producto.execution_module,
            guards=[],
            side_effects=[],
            required_args=[],
            status="active",
            runtime="python" if producto.execution_module else "unknown",
        )


class NormCatalogAdapter:
    """Adapta ``NormasDelCatalogo`` al protocolo ``NormCatalog`` de gobernanza.

    Proporciona acceso de solo lectura al catálogo de normas vigente.
    """

    def __init__(self, normas_del_catalogo: Any) -> None:
        self._normas = normas_del_catalogo

    def por_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        return self._normas.por_codigo(codigo)

    def vigentes(self) -> Sequence[Dict[str, Any]]:
        return self._normas.vigentes()

    def enforcement_de(self, tool_name: str) -> List[str]:
        """Devuelve la lista de códigos de norma que esta tool hace cumplir.

        Se deriva del campo ``guards`` de la tool en el catálogo de producto.
        """
        producto = catalogo_producto().get(tool_name)
        if producto is None:
            return []
        return getattr(producto, "guards", []) or []
