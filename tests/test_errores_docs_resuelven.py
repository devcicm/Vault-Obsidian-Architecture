"""QA-FL-15: every `recovery.docs` of the error catalog names a heading that exists.

An agent that follows `docs: "vault-obsidian-architecture.md §Vocabularios"`
looks for that heading. Measured on 2026-11-17, thirteen anchors named headings
that the documents do not have (or had no `§` at all), so the pointer led
nowhere. The anchor resolves the way the catalog writes it: the heading text
itself, or its leading code (`§AP-19` for `### AP-19 — Shadow indexing`).
Headings inside fenced code blocks are shell comments, not headings.
"""
from __future__ import annotations

import re
from typing import Dict, List

from apoyo import ROOT
from vault.kernel.errores import ERROR_CATALOG

_TITULO = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
_VALLA = re.compile(r"^\s*(```|~~~)")


def _titulos(documento: str) -> List[str]:
    titulos, en_bloque = [], False
    for linea in (ROOT / documento).read_text(encoding="utf-8").splitlines():
        if _VALLA.match(linea):
            en_bloque = not en_bloque
            continue
        m = None if en_bloque else _TITULO.match(linea)
        if m:
            titulos.append(m.group(1).strip())
    return titulos


def _resuelve(ancla: str, titulos: List[str]) -> bool:
    return any(t == ancla or t.startswith(ancla + " ") for t in titulos)


def _anclas() -> Dict[str, str]:
    return {codigo: e["recovery"]["docs"] for codigo, e in ERROR_CATALOG.items()
            if e["recovery"].get("docs")}


def test_fl15_cada_ancla_de_docs_resuelve_a_un_titulo_real():
    cache: Dict[str, List[str]] = {}
    rotas = []
    for codigo, docs in sorted(_anclas().items()):
        documento, _, ancla = docs.partition("§")
        documento, ancla = documento.strip(), ancla.strip()
        # Without `§` the whole document is the reference, and it must exist.
        if not (ROOT / documento).is_file():
            rotas.append((codigo, docs))
            continue
        if not ancla:
            continue
        titulos = cache.setdefault(documento, _titulos(documento))
        if not _resuelve(ancla, titulos):
            rotas.append((codigo, docs))
    assert rotas == []


def test_fl15_el_resolutor_no_acepta_un_prefijo_a_medias():
    titulos = ["AP-19 — Shadow indexing", "Grupo 15 — Índices de Navegación"]
    assert _resuelve("AP-19", titulos)
    assert _resuelve("Grupo 15 — Índices de Navegación", titulos)
    assert not _resuelve("AP-1", titulos)
    assert not _resuelve("Grupo 1", titulos)
