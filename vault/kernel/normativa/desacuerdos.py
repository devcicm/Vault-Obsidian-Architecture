"""Declared disagreements between notes: the `contradicts` predicate (PAT-7).

Two notes can disagree legitimately: two sources measured differently, two
teams chose differently, the evidence is not settled yet. A wiki that resolves
every contradiction by picking a winner loses the information that there was a
choice. PAT-7 lets the author declare it in the frontmatter of either note:

    contradicts: ["[[other-note]]"]

The predicate is the ontology's (`scripts/vault_ontology.json`, `contradicts`);
this module is the single reader of the declaration, shared by the AP-05
detector (`vault.gobernanza.fuente_unica`, which stops counting a declared
disagreement as debt) and the context pack (`vault_context_pack`, which then
delivers both sides). Two readers with their own parsing would disagree about
what was declared (AP-57), so both ask here. It lives in the kernel because
the two consumers sit in different bounded contexts.

Targets resolve like a wikilink, with `vault_lib.resolver_wikilink`: by file
name and `aliases:`, never by `title:` (AP-44). A target that resolves to zero
or several notes is not a declaration of anything and is ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set

#: The frontmatter key and ontology predicate. `tests/test_karpathy_desacuerdos.py`
#: fails if the ontology stops declaring it.
PREDICADO = "contradicts"


def destinos_declarados(frontmatter: Mapping[str, Any]) -> List[str]:
    """The raw targets of `contradicts:`; a string or a list of strings."""
    valor = frontmatter.get(PREDICADO) if isinstance(frontmatter, Mapping) else None
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        return []
    destinos = []
    for item in valor:
        if isinstance(item, str) and item.strip():
            bruto = item.strip()
            if bruto.startswith("[[") and bruto.endswith("]]"):
                bruto = bruto[2:-2]
            destinos.append(bruto)
    return destinos


def resolver_desacuerdos(
    frontmatter: Mapping[str, Any],
    desde: Optional[Path],
    indice: Mapping[str, Sequence[str]],
) -> List[str]:
    """The notes this note declares it contradicts, resolved to paths."""
    from vault_lib import resolver_wikilink

    rutas: Dict[str, None] = {}
    for destino in destinos_declarados(frontmatter):
        ruta, _candidatos = resolver_wikilink(destino, desde, dict(indice))
        if ruta:
            rutas.setdefault(ruta, None)
    return list(rutas)


def pares_declarados(
    frontmatter_por_ruta: Mapping[str, Mapping[str, Any]],
    indice: Mapping[str, Sequence[str]],
) -> Set[FrozenSet[str]]:
    """Every declared pair, symmetric: declaring it on either side is enough."""
    pares: Set[FrozenSet[str]] = set()
    for ruta, fm in frontmatter_por_ruta.items():
        for otra in resolver_desacuerdos(fm, Path(ruta), indice):
            if otra != ruta:
                pares.add(frozenset((ruta, otra)))
    return pares


def desacuerdo_declarado(
    valores: Mapping[str, Sequence[str]], pares: Set[FrozenSet[str]]
) -> bool:
    """Whether every pair of differing values is covered by a declared pair.

    `valores` maps each value to the notes that state it. A conflict is a
    declared disagreement only when, for every two values, some note stating
    one declared that it contradicts some note stating the other. A third
    note that silently disagrees keeps the conflict open.
    """
    grupos = [set(notas) for notas in valores.values()]
    if len(grupos) < 2:
        return False
    for i, a in enumerate(grupos):
        for b in grupos[i + 1:]:
            if not any(frozenset((x, y)) in pares for x in a for y in b if x != y):
                return False
    return True
