"""Qué cuenta como nota indexable — reexportado desde el núcleo.

superseded_by: vault/kernel/enumeracion.py (v40.34). El criterio no cambia: se
movió al núcleo para que la consulta pueda leerlo sin cruzar hacia Índices, y
este módulo se conserva (no-derogación) para quien ya lo importa por aquí.
"""

from __future__ import annotations

from ..kernel.enumeracion import NOMBRES_DE_INDICE, es_nota_indexable, notas_en_disco

__all__ = ["NOMBRES_DE_INDICE", "es_nota_indexable", "notas_en_disco"]
