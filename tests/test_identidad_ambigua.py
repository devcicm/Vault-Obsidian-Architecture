"""AP-17: un nombre que resuelve a dos notas es ambiguo, no de la primera que llegó.

`vault_graph._build_slug_map` registraba el stem con `if stem not in slug_map`:
con `01_Projects/overview.md` y `09_Infrastructure/overview.md`, `[[overview]]`
apuntaba siempre a la que `rglob` devolviera antes —un orden del sistema de
ficheros, no una decisión—, y la otra no aparecía en ninguna parte. Una
identidad que depende del orden de recorrido no es una identidad.

Ahora el resolvedor del dueño (`vault_lib`) devuelve los candidatos, el grafo
no inventa la arista y publica el enlace en `ambiguousLinks` con todas las
rutas; las notas cuyo nombre colapsa a la misma clave salen en
`nameCollisions`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402
from vault_lib import (  # noqa: E402
    colisiones_de_nombre,
    indice_de_destinos,
    indice_de_nombres,
    resolver_wikilink,
)


def test_ap17_el_indice_conserva_todos_los_candidatos():
    indice = indice_de_nombres(["01_Projects/overview.md", "09_Infra/overview.md"])
    assert indice["overview"] == ["01_Projects/overview.md", "09_Infra/overview.md"]
    assert indice["09_infra/overview"] == ["09_Infra/overview.md"]


def test_ap17_un_nombre_con_dos_notas_no_resuelve_a_ninguna():
    indice = indice_de_nombres(["01_Projects/overview.md", "09_Infra/overview.md"])
    assert resolver_wikilink("overview", None, indice) == (
        "",
        ["01_Projects/overview.md", "09_Infra/overview.md"],
    )
    # La carpeta lo desambigua, como en Obsidian.
    assert resolver_wikilink("09_Infra/overview|Vista", None, indice) == (
        "09_Infra/overview.md",
        ["09_Infra/overview.md"],
    )
    assert resolver_wikilink("no-existe", None, indice) == ("", [])


def test_ap17_un_alias_que_choca_con_un_nombre_es_ambiguo():
    indice = indice_de_nombres(
        ["07_K/redis.md", "07_K/cache.md"], {"07_K/cache.md": ["Redis"]}
    )
    assert resolver_wikilink("redis", None, indice)[0] == ""


def test_ap57_indice_de_destinos_deriva_del_indice_de_nombres():
    relativas = ["a/b/c.md", "d.md"]
    assert indice_de_destinos(relativas, ["Alias"]) == set(
        indice_de_nombres(relativas, {"": ["Alias"]})
    )


def test_ap17_colisiones_por_clave_de_nombre():
    colisiones = colisiones_de_nombre(
        ["01_P/Mi Proyecto.md", "07_K/mi-proyecto.md", "07_K/cmd.md", "07_K/c.md"]
    )
    assert colisiones == [
        {"clave": "miproyecto", "paths": ["01_P/Mi Proyecto.md", "07_K/mi-proyecto.md"]}
    ]


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "01_Projects", "07_Knowledge", "99_Index"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    vault_io.set_vault_root(tmp_path)
    return tmp_path


def test_ap17_el_grafo_no_elige_entre_dos_notas_homonimas(vault):
    import vault_graph

    (vault / "01_Projects" / "overview.md").write_text("---\ntitle: A\n---\n\nA\n", encoding="utf-8")
    (vault / "07_Knowledge" / "overview.md").write_text("---\ntitle: B\n---\n\nB\n", encoding="utf-8")
    (vault / "07_Knowledge" / "hub.md").write_text(
        "---\ntitle: Hub\n---\n\n[[overview]] [[07_Knowledge/overview]]\n", encoding="utf-8"
    )
    r = vault_graph.vault_graph()
    grafo = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))

    hacia = [e["to"] for e in grafo["edges"] if e["from"] == "07_Knowledge/hub.md"]
    assert hacia == ["07_Knowledge/overview.md"], hacia
    assert grafo["ambiguousLinks"] == [
        {
            "from": "07_Knowledge/hub.md",
            "link": "overview",
            "candidates": ["01_Projects/overview.md", "07_Knowledge/overview.md"],
        }
    ]
    assert grafo["nameCollisions"] == [
        {"clave": "overview", "paths": ["01_Projects/overview.md", "07_Knowledge/overview.md"]}
    ]
    assert r["stats"]["ambiguousLinks"] == 1
    assert r["stats"]["nameCollisions"] == 1
    # Ambiguo no es roto: el destino existe, sobra.
    assert grafo["brokenLinks"] == []


def test_ap17_el_grafo_resuelve_por_alias(vault):
    import vault_graph

    (vault / "07_Knowledge" / "cache.md").write_text(
        "---\ntitle: Cache\naliases: [Redis]\n---\n\nC\n", encoding="utf-8"
    )
    (vault / "07_Knowledge" / "hub.md").write_text(
        "---\ntitle: Hub\n---\n\n[[Redis]]\n", encoding="utf-8"
    )
    vault_graph.vault_graph()
    grafo = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert [e["to"] for e in grafo["edges"]] == ["07_Knowledge/cache.md"]
