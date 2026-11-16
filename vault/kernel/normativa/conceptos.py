"""What a text marks as an entity, and when a concept deserves its own page (AP-71).

The entity rule lived inside `vault_ingest._extract_entities`. A second
consumer needs it — the AP-71 lint in `vault_audit`, which looks for terms that
many notes mention and no note owns — and two copies of the rule would drift
(AP-57). Ingest (consulta) and audit (gobernanza) cannot import each other
without crossing a context boundary, so the owner lives in the kernel, which
both already depend on.

The rule is deterministic on purpose: only what the text itself marks as an
entity counts. Nothing is inferred by similarity; a false positive here becomes
a ghost note or a broken wikilink, which is worse than not extracting at all.

Resolution follows the consumer's criterion (rule 7, AP-44): a concept has a
page when a note answers to it by file name or `aliases:` —never by `title:`,
which Obsidian ignores—, tried verbatim and as the slug the write path would
give it (`vault_write` names files with `slugify(title)`).
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from ..normalizacion import slugify
from ..regex import strip_code_blocks

#: Frequent lexical noise in technical text that passes the capitalisation
#: filter without being a domain entity.
ENTIDADES_STOPWORDS = frozenset({
    "The", "This", "That", "These", "Those", "There", "When", "Where", "What",
    "With", "From", "Para", "Este", "Esta", "Estos", "Cuando", "Donde", "Como",
    "Nota", "Note", "Ver", "See", "TODO", "FIXME", "OK",
})

#: AP-71: how many distinct notes must mention a term before its missing page
#: is reported. Three is the smallest count that is not a coincidence between
#: two notes written in the same session; it is declared, not calibrated.
UMBRAL_CONCEPTO = 3

#: The entity kinds that name a concept (as opposed to a URL, a path or a tag).
CLASES_DE_CONCEPTO = ("proper_nouns", "acronyms")

_RE_WIKILINK = re.compile(r"\[\[([^\]|#]+)")
_RE_TAG = re.compile(r"(?<!\w)#([A-Za-z][\w/-]{1,30})")
_RE_URL = re.compile(r"https?://[^\s<>()\"']+")
_RE_CODIGO = re.compile(r"`([A-Za-z_][\w.]{2,40})`")
_RE_RUTA = re.compile(r"\b[\w./-]+\.(?:md|py|js|ts|json|yaml|yml)\b")
_RE_NOMBRE_PROPIO = re.compile(r"\b(?:[A-Z][a-z]{2,}\s){1,3}[A-Z][a-z]{2,}\b")
_RE_SIGLA = re.compile(r"\b[A-Z]{2,6}\b")


def _dedup(items: Iterable[str], limite: int) -> List[str]:
    return list(dict.fromkeys(i.strip() for i in items if i.strip()))[:limite]


def extraer_entidades(texto: str) -> Dict[str, List[str]]:
    """Deterministic extraction: only what the text marks as an entity.

    A wikilink inside a fence is code the text shows, not a destination:
    Obsidian does not resolve it, so it is not extracted (the fence criterion
    belongs to `vault.kernel.regex.strip_code_blocks`, AP-57).
    """
    sin_codigo = strip_code_blocks(texto)
    proper = [m for m in _RE_NOMBRE_PROPIO.findall(texto)
              if m.split()[0] not in ENTIDADES_STOPWORDS]
    # Two or more capitalised words in a row: with one, noise beats signal.
    acronyms = [a for a in _RE_SIGLA.findall(texto) if a not in ENTIDADES_STOPWORDS]
    return {
        "wikilinks": _dedup(_RE_WIKILINK.findall(sin_codigo), 30),
        "tags": _dedup([t.lower() for t in _RE_TAG.findall(texto)], 20),
        "urls": _dedup(_RE_URL.findall(texto), 20),
        "code_refs": _dedup(_RE_CODIGO.findall(texto), 20),
        "paths": _dedup(_RE_RUTA.findall(texto), 20),
        "proper_nouns": _dedup(proper, 20),
        "acronyms": _dedup(acronyms, 20),
    }


def terminos_de_concepto(texto: str) -> List[str]:
    """The concept terms of a text: proper nouns and acronyms, code excluded.

    The lint reads note bodies, where a fence is an example, not a claim; the
    same `strip_code_blocks` owner decides what a fence is.
    """
    # A file name is a path, not a concept: `AGENTS.md` matched the acronym
    # pattern and came out as the concept `AGENTS` in the rule-7 contrast
    # (scrap_* corpora, 2026-11-16). Paths are removed before extracting.
    entidades = extraer_entidades(_RE_RUTA.sub(" ", strip_code_blocks(texto)))
    return _dedup((t for clase in CLASES_DE_CONCEPTO for t in entidades[clase]), 40)


def formas_de_resolucion(termino: str) -> Tuple[str, ...]:
    """The names a note could answer to for `termino`: verbatim and slugged."""
    return tuple(dict.fromkeys(f for f in (termino.strip().lower(), slugify(termino)) if f))


def resolver_concepto(termino: str, indice: Mapping[str, Sequence[str]]) -> List[str]:
    """The notes that answer to `termino`, with the Obsidian criterion.

    `indice` is `vault_lib.indice_de_nombres(...)`: path suffixes and aliases,
    never titles. Every candidate is returned; ambiguity is the caller's call.
    """
    vistos: Dict[str, None] = {}
    for forma in formas_de_resolucion(termino):
        for ruta in indice.get(forma, ()):
            vistos.setdefault(ruta, None)
    return list(vistos)


def conceptos_sin_pagina(
    terminos_por_nota: Mapping[str, Iterable[str]],
    indice: Mapping[str, Sequence[str]],
    umbral: int = UMBRAL_CONCEPTO,
) -> List[Dict[str, object]]:
    """AP-71: terms mentioned by `umbral` or more notes that no note owns.

    `terminos_por_nota` maps a note path to its concept terms. A note that
    mentions a term counts once, however often it repeats it. The result is
    ordered by how many notes mention the term, then by the term.
    """
    notas_por_termino: Dict[str, List[str]] = {}
    for ruta, terminos in terminos_por_nota.items():
        for termino in dict.fromkeys(terminos):
            notas_por_termino.setdefault(termino, []).append(ruta)
    hallazgos = [
        {"term": termino, "notes": len(notas), "examples": sorted(notas)[:3]}
        for termino, notas in notas_por_termino.items()
        if len(notas) >= umbral and not resolver_concepto(termino, indice)
    ]
    hallazgos.sort(key=lambda h: (-int(h["notes"]), str(h["term"])))
    return hallazgos
