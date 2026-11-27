"""Tests de paquete de la ID norma AP-80 (sello epistémico en aristas)."""

from vault.grafo.aristas import (
    CONFIANZA_EPISTEMICA,
    clasificar_arista_epistemica,
    consolidar_aristas,
    estampar_epistemica,
)


def test_ap80_sello_epistemico_canonico():
    assert CONFIANZA_EPISTEMICA == ("EXTRACTED", "INFERRED", "AMBIGUOUS")
    aristas = [
        estampar_epistemica(a)
        for a in consolidar_aristas([
            {"from": "a.md", "to": "b.md", "type": "wiki-link"},
            {"from": "a.md", "to": "c.md", "predicate": "shared_tag"},
            {"from": "a.md", "to": "d.md", "predicate": "heuristica_desconocida"},
        ])
    ]
    assert [(a["epistemic"], a["confidence"]) for a in aristas] == [
        ("EXTRACTED", 1.0),
        ("INFERRED", 0.75),
        ("AMBIGUOUS", 0.5),
    ]
    assert clasificar_arista_epistemica({"predicate": "implements"}) == ("EXTRACTED", 1.0)
