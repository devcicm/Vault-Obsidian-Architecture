"""Hoja canónica de nombres reservados de índice.

AP-57: el dueño de este criterio es vault/kernel. Definido aquí para que
los módulos de vault/ puedan consultarlo sin cruzar la frontera scripts→vault
en la wheel instalada.

Nombres completos (con .md):
  "index.md", "readme.md"
"""

from __future__ import annotations

RESERVED_INDEX_NAMES: frozenset[str] = frozenset({"index.md", "readme.md"})
"""Nombres de fichero (con .md) reservados para índices generados automáticamente."""

RESERVED_INDEX_STEMS: frozenset[str] = frozenset({"index", "readme"})
"""Stems sin extensión — para comparar con slugify_strict output."""


def es_nombre_reservado(nombre: str) -> bool:
    """True si ``nombre`` (con o sin ``.md``) es el de un índice generado.

    Sin distinguir mayúsculas: en Windows y macOS ``Index.md`` e ``index.md``
    son el mismo fichero, así que una nota titulada «Index» acaba siendo el
    índice que ``vault_section_index`` regenera encima — el contenido del
    usuario solo sobrevive en un backup oculto. Toda entrada que deriva un
    nombre de un título pregunta aquí antes de escribir (AP-57: un solo dueño).
    """
    base = (nombre or "").strip().lower()
    if base.endswith(".md"):
        base = base[:-3]
    return base in RESERVED_INDEX_STEMS
