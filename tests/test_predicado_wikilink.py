"""AP-57: el wikilink se llama de una sola manera para quien consulta el grafo.

`graph.json` escribe sus aristas como `"type": "wiki-link"` —nombre legacy que
el contrato de campos conserva— y `graph-enriched.json` como
`"predicate": "wiki_link"`. Las consultas leían `predicate or type` sin
traducir: sobre el grafo básico la tabla de pesos de `vault_subgraph` no
encontraba `wiki-link` y le daba el peso por defecto (0.5 en vez de 1.0), y
`--predicate wiki_link` en `vault_subgraph` y `vault_impact` devolvía vacío.
Medido en v40.x con `vault_write` + `vault_graph` sobre un vault limpio.

La traducción tiene un dueño, `vault.grafo.aristas.predicado_de`; el fichero
no se reescribe —`id` y `type` siguen siendo los que leen los consumidores—.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_io  # noqa: E402
from vault.grafo.aristas import PREDICADO_WIKILINK, predicado_de  # noqa: E402

_BASICA = {"from": "07_Knowledge/a.md", "to": "07_Knowledge/b.md", "type": "wiki-link"}


def test_ap57_el_tipo_legacy_se_lee_como_el_predicado_canonico():
    assert PREDICADO_WIKILINK == "wiki_link"
    assert predicado_de(_BASICA) == "wiki_link"
    assert predicado_de({"predicate": "depends_on", "type": "wiki-link"}) == "depends_on"
    assert predicado_de({"type": "deleted-node"}) == "deleted-node"
    assert predicado_de({}) == "wiki_link"


def test_ap57_subgraph_pesa_el_wikilink_del_grafo_basico_con_su_peso():
    import vault_subgraph as VS

    grafo = {"nodes": {}, "edges": [_BASICA]}
    [(_, predicado, peso)] = VS._adjacency(grafo, "out", None)["07_Knowledge/a.md"]
    assert (predicado, peso) == ("wiki_link", VS.PREDICATE_WEIGHT["wiki_link"])
    assert VS._adjacency(grafo, "out", {"wiki_link"}), "--predicate wiki_link no lo encuentra"


def test_ap57_impact_filtra_el_wikilink_del_grafo_basico(tmp_path):
    (tmp_path / "99_Index").mkdir()
    (tmp_path / "99_Index" / "graph.json").write_text(
        json.dumps({"nodes": {}, "edges": [_BASICA]}), encoding="utf-8"
    )
    vault_io.set_vault_root(tmp_path)
    import vault_impact

    assert vault_impact._load_graph(predicate_filter=["wiki_link"])["edges"] == [_BASICA]
