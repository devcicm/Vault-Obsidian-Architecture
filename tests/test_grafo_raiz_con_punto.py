"""AP-44: un vault colgado de un directorio con punto no es un vault vacío.

`vault_graph` y `vault_graph_merge` descartaban las notas con algún tramo
oculto mirando la ruta **absoluta** (`p.parts`): un vault en
`~/.claude/vault-standard/` —donde vive uno de los consumidores del estándar—
salía con cero nodos y cero aristas, sin error. `vault_reindex` tuvo el mismo
fallo y se corrigió en `vault.kernel.enumeracion`, que mide la ruta relativa
al vault; los dos productores del grafo seguían con su propia copia del
criterio (AP-57). Ahora enumeran con `notas_en_disco`, el mismo enumerador que
usa `vault_subgraph` para declarar el desfase.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / ".claude" / "vault-x"
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    (raiz / "07_Knowledge" / "a.md").write_text("---\ntitle: A\n---\n\n[[b]]\n", encoding="utf-8")
    (raiz / "07_Knowledge" / "b.md").write_text("---\ntitle: B\n---\n\nb\n", encoding="utf-8")
    (raiz / "07_Knowledge" / ".oculta").mkdir()
    (raiz / "07_Knowledge" / ".oculta" / "c.md").write_text("---\ntitle: C\n---\n", encoding="utf-8")
    vault_io.set_vault_root(raiz)
    return raiz


def test_vault_graph_mide_el_vault_y_no_la_maquina(vault):
    import vault_graph

    vault_graph.vault_graph()
    g = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert sorted(g["nodes"]) == ["07_Knowledge/a.md", "07_Knowledge/b.md"]
    assert [(e["from"], e["to"]) for e in g["edges"]] == [("07_Knowledge/a.md", "07_Knowledge/b.md")]


def test_vault_graph_merge_mide_el_vault_y_no_la_maquina(vault):
    import vault_graph_merge

    vault_graph_merge.vault_graph_merge()
    g = json.loads((vault / "99_Index" / "graph-enriched.json").read_text(encoding="utf-8"))
    assert sorted(g["nodes"]) == ["07_Knowledge/a.md", "07_Knowledge/b.md"]
