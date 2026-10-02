"""Una arista es una relación, no una aparición: identidad `(from, predicate, to)`.

Los dos productores del grafo añadían una arista por cada vez que el enlace
aparecía en la nota. Tres `[[cache]]` en la misma nota eran tres aristas
iguales, `totalEdges` contaba apariciones y `vault_impact`/`vault_delta`
listaban el mismo origen tres veces en su grafo inverso. Ahora cada relación
sale una vez, con `id` estable, y `occurrences` conserva cuántas veces se
escribió; si dos declaraciones de la misma relación difieren en un atributo
(`label`, `cardinality`…), las otras se guardan en `variants` en vez de
perderse.

El campo no se llama `weight` a propósito: `vault_subgraph` ya llama así al
peso del predicado, y dos significados para un mismo nombre en el mismo
contexto es el conflicto que se quiere evitar.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402
from vault.grafo.aristas import consolidar_aristas  # noqa: E402


def test_una_arista_por_relacion_con_sus_apariciones():
    a = {"from": "a.md", "to": "b.md", "predicate": "wiki_link", "source": "wikilinks"}
    c = {"from": "a.md", "to": "c.md", "predicate": "wiki_link", "source": "wikilinks"}
    assert consolidar_aristas([a, dict(a), c, dict(a)]) == [
        {"id": "a.md|wiki_link|b.md", **a, "occurrences": 3},
        {"id": "a.md|wiki_link|c.md", **c, "occurrences": 1},
    ]


def test_el_tipo_legacy_cuenta_como_predicado():
    a = {"from": "a.md", "to": "b.md", "type": "wiki-link"}
    [unica] = consolidar_aristas([a, dict(a)])
    assert unica["id"] == "a.md|wiki-link|b.md" and unica["occurrences"] == 2


def test_los_atributos_distintos_no_se_pierden():
    base = {"from": "A", "to": "B", "predicate": "depends_on", "source": "entity_relations"}
    [unica] = consolidar_aristas([
        {**base, "label": "usa", "cardinality": "1:N"},
        {**base, "label": "usa", "cardinality": "1:N"},
        {**base, "label": "lee", "cardinality": "1:N"},
    ])
    assert unica["label"] == "usa" and unica["occurrences"] == 3
    assert unica["variants"] == [{"label": "lee"}]


def test_no_muta_la_entrada():
    a = {"from": "a.md", "to": "b.md", "predicate": "wiki_link"}
    consolidar_aristas([a, a])
    assert a == {"from": "a.md", "to": "b.md", "predicate": "wiki_link"}


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    (tmp_path / "07_Knowledge" / "cache.md").write_text("---\ntitle: C\n---\n\nC\n", encoding="utf-8")
    (tmp_path / "07_Knowledge" / "hub.md").write_text(
        "---\ntitle: Hub\n---\n\n[[cache]] y otra vez [[cache]] y [[cache|la caché]]\n",
        encoding="utf-8",
    )
    vault_io.set_vault_root(tmp_path)
    return tmp_path


def test_vault_graph_emite_aristas_unicas(vault):
    import vault_graph

    r = vault_graph.vault_graph()
    grafo = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert grafo["edges"] == [{
        "id": "07_Knowledge/hub.md|wiki-link|07_Knowledge/cache.md",
        "from": "07_Knowledge/hub.md",
        "to": "07_Knowledge/cache.md",
        "type": "wiki-link",
        "occurrences": 3,
    }]
    assert r["stats"]["totalEdges"] == 1


def test_vault_graph_merge_emite_aristas_unicas(vault):
    import vault_graph_merge

    r = vault_graph_merge.vault_graph_merge()
    g = json.loads((vault / "99_Index" / "graph-enriched.json").read_text(encoding="utf-8"))
    wiki = [e for e in g["edges"] if e["predicate"] == "wiki_link"]
    assert len(wiki) == 1 and wiki[0]["occurrences"] == 3
    assert wiki[0]["id"] == "07_Knowledge/hub.md|wiki_link|07_Knowledge/cache.md"
    assert r["metadata"]["wiki_edges"] == 1
