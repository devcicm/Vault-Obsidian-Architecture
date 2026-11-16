"""Corpus sintetico etiquetado: mide empaquetado, no precision de busqueda real."""

import pytest
import vault_context_pack as pack


CORPUS = {
    "07_Knowledge/relevante.md": "hallazgo " * 80,
    "07_Knowledge/secundaria.md": "contexto secundario " * 10,
}
CASOS = [
    {"query": "inventario", "expected": {"07_Knowledge/relevante.md"}, "top_k": 2, "excerpt": 10, "recall": 1.0, "omitidas": 0, "truncadas": 1},
    {"query": "inventario", "expected": set(CORPUS), "top_k": 1, "excerpt": 500, "recall": 0.5, "omitidas": 1, "truncadas": 0},
]


@pytest.mark.parametrize("caso", CASOS)
def test_metrica_basica_de_recuperacion_omisiones_y_truncado(monkeypatch, caso):
    monkeypatch.setattr(pack, "vault_query_parse", lambda q: {
        "ok": True, "confidence": 1.0,
        "structured": {"phrases": [], "terms": [q], "tags": [], "sections_named": [],
                       "seeds": [], "hops": 1, "status": [], "temporal": None}})
    monkeypatch.setattr(pack, "vault_search", lambda *a, **k: {"ok": True, "results": [
        {"path": p, "score": 2 if "relevante" in p else 1} for p in CORPUS]})
    monkeypatch.setattr(pack, "vault_subgraph", lambda **k: {"ok": True, "nodes": []})
    monkeypatch.setattr(pack, "_read_note", lambda p: {
        "ok": True, "frontmatter": {"title": p}, "body": CORPUS[p]})
    resultado = pack.vault_context_pack(caso["query"], budget_tokens=3000,
        top_k=caso["top_k"], excerpt_tokens=caso["excerpt"], include_preferences=False)
    assert resultado["ok"], resultado
    incluidas = {x["path"] for x in resultado["included"]}
    recuperadas = caso["expected"] & incluidas
    recall = len(recuperadas) / len(caso["expected"])
    omitidas = len(caso["expected"] - incluidas)
    truncadas = sum(x["truncated"] for x in resultado["included"] if x["path"] in caso["expected"])
    assert (recall, omitidas, truncadas) == (caso["recall"], caso["omitidas"], caso["truncadas"])
