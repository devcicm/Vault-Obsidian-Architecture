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
