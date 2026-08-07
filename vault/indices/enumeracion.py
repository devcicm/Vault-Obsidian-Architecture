"""Qué cuenta como nota indexable. Una sola definición, con sus variantes explícitas.

`vault_reindex` y `vault_tags` tenían cada uno su `_is_vault_note`. No eran
iguales —el de etiquetas además salta `index.md` y `readme.md`— y esa diferencia
real es la razón por la que **no** se unifican a la fuerza: un índice de
búsqueda que dejara de listar los `index.md` cambiaría lo que `vault_search`
encuentra, y eso es contrato.

Lo que sí se corrige es que la diferencia fuera implícita. Aquí es un argumento
con nombre: quien enumera declara si quiere los índices o no, y las dos ramas se
leen juntas. Que `--check` y `--fix` compartan enumerador ya estaba resuelto en
v39 (AP-44); esto lo extiende al contexto entero.

**Un cambio de comportamiento, declarado.** `vault_reindex` descartaba las notas
con algún tramo oculto mirando la ruta **absoluta**: un vault colgado de un
directorio con punto —`~/.claude/vault-x/`, que es exactamente donde viven
varios de este usuario— se indexaba entero como vacío, sin error. El criterio
que queda es el relativo, que es el que ya usaba `vault_tags`: se mide el vault,
no la disposición de la máquina que lo aloja (AP-44). Es una corrección, no una
unificación cosmética, y por eso va con test propio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

#: Ficheros que son índice, no contenido. Son navegación generada por este mismo
#: contexto: indexar la salida del indexador es contarse a uno mismo.
NOMBRES_DE_INDICE = frozenset({"index.md", "readme.md"})


def es_nota_indexable(
    ruta: Path,
    raiz: Path,
    secciones: Iterable[str],
    incluir_indices: bool = True,
) -> bool:
    """True si `ruta` es una nota del vault según el criterio del contexto.

    Las tres condiciones son las que ya estaban, en el mismo orden:
    dentro de la raíz, colgando de una sección canónica (nunca suelta en la
    raíz — eso es AP-15) y sin ningún tramo oculto.
    """
    try:
        partes = Path(ruta).relative_to(raiz).parts
    except ValueError:
        return False
    if len(partes) < 2:
        return False
    if partes[0] not in set(secciones):
        return False
    if any(p.startswith(".") for p in partes):
        return False
    if not incluir_indices and Path(ruta).name.lower() in NOMBRES_DE_INDICE:
        return False
    return True


def notas_en_disco(
    raiz: Path,
    secciones: Iterable[str],
    incluir_indices: bool = True,
) -> List[Path]:
    """Las notas que una reconstrucción tocaría, con SU mismo criterio.

    Compartir enumerador entre la comprobación y la reconstrucción es lo que
    impide que `--check` mida una cosa y `--fix` arregle otra (AP-44).
    """
    secciones = set(secciones)
    return [
        p
        for p in Path(raiz).rglob("*.md")
        if es_nota_indexable(p, raiz, secciones, incluir_indices)
    ]
