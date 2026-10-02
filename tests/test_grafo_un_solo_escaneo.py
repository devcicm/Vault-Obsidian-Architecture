"""Los dos productores del grafo leen las notas con un solo escaneo y con el dueño.

`vault_graph` y `vault_graph_merge` recorrían el vault cada uno a su manera y
leían `title:` y `tags:` con un regex por líneas sobre el frontmatter: las
etiquetas en lista de bloque (`tags:` + `- api`), en flujo sin comillas
(`[api, demo]`) o en una nota con fin de línea CRLF salían `[]`, y una nota
CRLF perdía además su título. Es AP-44: una medida que lee con su propio
criterio y no con el del consumidor (`yaml.safe_load`). `vault-sandbox/` lo
escribe este repo con JSON entre comillas y no podía exhibirlo.

Ahora `vault_lib.escanear_wikilinks` es el único escaneo —frontmatter por
`parse_frontmatter`, enlaces por el resolvedor de Obsidian— y cada productor
solo proyecta su esquema: `type: "wiki-link"` en `graph.json`,
`predicate: "wiki_link"` en `graph-enriched.json`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402
from vault_lib import escanear_wikilinks  # noqa: E402

_NOTAS = {
    "07_Knowledge/bloque.md": "---\ntitle: Bloque\ntags:\n  - api\n  - demo\n---\n\n[[flujo]]\n",
    "07_Knowledge/flujo.md": "---\ntitle: Flujo\ntags: [api, demo]\n---\n\n[[crlf]] [[nada]]\n",
    "07_Knowledge/crlf.md": "---\r\ntitle: Con CRLF\r\ntags: [\"api\"]\r\n---\r\n\r\n[[bloque]]\r\n",
}


def test_el_escaneo_lee_el_frontmatter_con_el_duenio():
    e = escanear_wikilinks(_NOTAS)
    assert e["notas"]["07_Knowledge/bloque.md"]["tags"] == ["api", "demo"]
    assert e["notas"]["07_Knowledge/flujo.md"]["tags"] == ["api", "demo"]
    assert e["notas"]["07_Knowledge/crlf.md"]["title"] == "Con CRLF"
    assert e["notas"]["07_Knowledge/crlf.md"]["tags"] == ["api"]
    assert sorted((a["from"], a["to"]) for a in e["aristas"]) == [
        ("07_Knowledge/bloque.md", "07_Knowledge/flujo.md"),
        ("07_Knowledge/crlf.md", "07_Knowledge/bloque.md"),
        ("07_Knowledge/flujo.md", "07_Knowledge/crlf.md"),
    ]
    assert [r["link"] for r in e["rotos"]] == ["nada"]


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    for rel, texto in _NOTAS.items():
        (tmp_path / rel).write_bytes(texto.encode("utf-8"))
    vault_io.set_vault_root(tmp_path)
    return tmp_path


def test_vault_graph_proyecta_el_escaneo_compartido(vault):
    import vault_graph

    vault_graph.vault_graph()
    g = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert g["nodes"]["07_Knowledge/bloque.md"]["tags"] == ["api", "demo"]
    assert g["nodes"]["07_Knowledge/crlf.md"]["title"] == "Con CRLF"
    assert {e["type"] for e in g["edges"]} == {"wiki-link"}
    assert len(g["edges"]) == 3


def test_vault_graph_merge_proyecta_el_mismo_escaneo(vault):
    import vault_graph
    import vault_graph_merge

    vault_graph.vault_graph()
    plano = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    vault_graph_merge.vault_graph_merge()
    g = json.loads((vault / "99_Index" / "graph-enriched.json").read_text(encoding="utf-8"))
    assert g["nodes"]["07_Knowledge/flujo.md"]["tags"] == ["api", "demo"]
    assert g["nodes"]["07_Knowledge/crlf.md"]["title"] == "Con CRLF"
    wiki = sorted((e["from"], e["to"]) for e in g["edges"] if e["predicate"] == "wiki_link")
    assert wiki == sorted((e["from"], e["to"]) for e in plano["edges"])
