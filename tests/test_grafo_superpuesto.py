"""AP-57: las consultas leen el mismo grafo, y no pierden lo tipado por leer el fresco.

`vault_subgraph` usaba el enriquecido solo si no era más viejo que el básico, y
desde que el básico se refresca en cada escritura (AP-47) eso no pasaba nunca:
los predicados tipados y la `class` desaparecían de las consultas.
`vault_impact` hacía lo contrario —el enriquecido siempre—, así que no veía las
notas escritas después del último `vault_graph_merge`. Dos criterios para la
misma pregunta, y cada uno perdía una mitad.

El dueño es `vault.grafo.lectura.grafo_para_consulta`: la base es el básico y
del enriquecido se toman las aristas tipadas cuyos extremos siguen vivos.
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_io  # noqa: E402
from vault.grafo.lectura import superponer  # noqa: E402

A, B, NUEVA = "07_Knowledge/a.md", "07_Knowledge/b.md", "07_Knowledge/nueva.md"


def _nodo(titulo):
    return {"title": titulo, "type": "07_Knowledge", "tags": [], "aliases": [], "links": []}


@pytest.fixture
def vault(tmp_path):
    """Un básico al día con una nota que el enriquecido, más viejo, no conoce."""
    indices = tmp_path / "99_Index"
    indices.mkdir()
    conocimiento = tmp_path / "07_Knowledge"
    conocimiento.mkdir()
    for nombre in ("a", "b", "nueva"):
        (conocimiento / f"{nombre}.md").write_text(f"# {nombre}\n", encoding="utf-8")
    basico = {
        "nodes": {A: _nodo("a"), B: _nodo("b"), NUEVA: _nodo("nueva")},
        "edges": [{"from": NUEVA, "to": A, "type": "wiki-link"}],
    }
    enriquecido = {
        "nodes": {A: {**_nodo("a"), "class": "concept"}, B: {**_nodo("b"), "class": "decision"}},
        "edges": [
            {"from": A, "to": B, "predicate": "depends_on"},
            {"from": A, "to": "07_Knowledge/borrada.md", "predicate": "depends_on"},
            {"from": B, "to": A, "predicate": "wiki_link"},
        ],
    }
    (indices / "graph-enriched.json").write_text(json.dumps(enriquecido), encoding="utf-8")
    viejo = time.time() - 3600
    os.utime(indices / "graph-enriched.json", (viejo, viejo))
    (indices / "graph.json").write_text(json.dumps(basico), encoding="utf-8")
    vault_io.set_vault_root(tmp_path)
    return tmp_path


def test_ap57_subgraph_ve_la_nota_nueva_y_la_arista_tipada(vault):
    import vault_subgraph as VS

    env = VS.vault_subgraph([NUEVA], hops=2)
    assert env["ok"] is True, env
    rutas = {n["path"] for n in env["nodes"]}
    assert {NUEVA, A, B} <= rutas, "la arista depends_on del enriquecido no llegó"
    assert any(e.get("predicate") == "depends_on" for e in env["edges"]), env["edges"]
    assert env["stats"]["graph_source"] == "graph.json"
    assert env["stats"]["overlay"]["typed_edges"] == 1
    assert env["stats"]["overlay"]["dropped_edges"] == 1


def test_ap57_la_clase_del_enriquecido_filtra_sobre_el_basico(vault):
    import vault_subgraph as VS

    env = VS.vault_subgraph([A], hops=1, node_class="decision")
    assert env["ok"] is True, env
    assert B in {n["path"] for n in env["nodes"]}


def test_ap57_impact_filtra_lo_tipado_sin_perder_lo_nuevo(vault):
    import vault_impact

    tipado = vault_impact._load_graph(predicate_filter=["depends_on"])
    assert [(e["from"], e["to"]) for e in tipado["edges"]] == [(A, B)]
    todo = vault_impact._load_graph()
    assert NUEVA in todo["nodes"], "vault_impact sigue leyendo el enriquecido viejo"
    afectadas = vault_impact.vault_impact([A])["impacted"]
    assert NUEVA in {n["path"] for n in afectadas}


def test_ap37_un_enriquecido_ilegible_se_declara_y_no_tumba_la_consulta(vault):
    (vault / "99_Index" / "graph-enriched.json").write_text("{roto", encoding="utf-8")
    import vault_subgraph as VS

    env = VS.vault_subgraph([NUEVA], hops=1)
    assert env["ok"] is True, env
    assert env["stats"]["overlay"]["applied"] is False
    assert env["stats"]["overlay"]["reason"] == "enriched_unreadable"


def test_superponer_no_duplica_ni_toma_wikilinks_del_enriquecido():
    basico = {"nodes": {A: _nodo("a"), B: _nodo("b")},
              "edges": [{"from": A, "to": B, "type": "wiki-link"}]}
    enriquecido = {"nodes": [], "edges": [
        {"from": A, "to": B, "predicate": "wiki_link"},
        {"from": A, "to": B, "predicate": "depends_on"},
        {"from": A, "to": B, "predicate": "depends_on"},
    ]}
    grafo = superponer(basico, enriquecido)
    assert len(grafo["edges"]) == 2
    assert grafo["overlay"]["typed_edges"] == 1
    assert basico["edges"] == [{"from": A, "to": B, "type": "wiki-link"}], "muta la entrada"
