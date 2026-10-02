"""AP-17: en `vault_graph_merge` lo parecido es una sugerencia, no una arista.

Tres vías fijaban un extremo sin que el vault lo dijera:

- `stem_map[title_stem] = rel`: un `[[Arquitectura]]` resolvía a la nota cuyo
  `title:` era «Arquitectura», que Obsidian no mira (regla 7). La arista
  existía en el grafo y el enlace salía roto en el editor.
- la última nota con un stem normalizado pisaba a la anterior en `stem_map`;
- `_fuzzy_resolve` (SequenceMatcher ≥ 0.75) daba por resuelta una entidad
  `UserServce` contra `user-service.md`: la arista se creaba con un parecido.

Ahora la identidad es exacta —el enlace con el criterio de Obsidian, el nombre
de una entidad o un fichero de código con `clave_de_nombre` sobre nombre de
fichero y `aliases:`— y todo lo demás sale en `suggestions` con su criterio y
sus candidatos, para que lo confirme quien conoce el vault.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402


def _nota(raiz, rel, cuerpo="", **fm):
    ruta = raiz / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cabecera = "".join(f"{k}: {v}\n" for k, v in fm.items())
    ruta.write_text(f"---\n{cabecera}---\n\n{cuerpo}\n", encoding="utf-8")


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "06_Diagrams/entity", "07_Knowledge", "11_Code", "99_Index"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    vault_io.set_vault_root(tmp_path)
    return tmp_path


def _enriquecido(vault):
    import vault_graph_merge

    r = vault_graph_merge.vault_graph_merge()
    return r, json.loads((vault / "99_Index" / "graph-enriched.json").read_text(encoding="utf-8"))


def _wiki(g, desde):
    return sorted(e["to"] for e in g["edges"] if e["from"] == desde and e["predicate"] == "wiki_link")


def test_ap17_el_title_no_resuelve_un_wikilink(vault):
    _nota(vault, "07_Knowledge/arq-v2.md", "x", title="Arquitectura")
    _nota(vault, "07_Knowledge/hub.md", "[[Arquitectura]]", title="Hub")
    r, g = _enriquecido(vault)
    assert _wiki(g, "07_Knowledge/hub.md") == []
    assert [b["link"] for b in g["brokenLinks"]] == ["Arquitectura"]
    assert {
        "source": "wikilinks",
        "from": "07_Knowledge/hub.md",
        "endpoint": "Arquitectura",
        "criterion": "title",
        "candidates": ["07_Knowledge/arq-v2.md"],
    } in g["suggestions"]
    assert r["stats"]["suggestions"] >= 1


def test_ap17_el_wikilink_ambiguo_no_crea_arista(vault):
    _nota(vault, "07_Knowledge/overview.md", "a", title="A")
    _nota(vault, "11_Code/overview.md", "b", title="B")
    _nota(vault, "07_Knowledge/hub.md", "[[overview]] [[11_Code/overview]]", title="Hub")
    _, g = _enriquecido(vault)
    assert _wiki(g, "07_Knowledge/hub.md") == ["11_Code/overview.md"]
    assert g["ambiguousLinks"] == [
        {
            "from": "07_Knowledge/hub.md",
            "link": "overview",
            "candidates": ["07_Knowledge/overview.md", "11_Code/overview.md"],
        }
    ]


def test_ap17_el_wikilink_se_resuelve_como_en_obsidian(vault):
    _nota(vault, "07_Knowledge/cache.md", "c", title="Cache", aliases="[Redis]")
    _nota(vault, "07_Knowledge/hub.md", "[[Redis]] [[cache|la caché]] [[cache#Uso]]", title="Hub")
    _, g = _enriquecido(vault)
    assert _wiki(g, "07_Knowledge/hub.md") == ["07_Knowledge/cache.md"] * 3


def _relaciones(vault, *pares):
    (vault / "06_Diagrams" / "entity" / "demo-relations.json").write_text(
        json.dumps({
            "project": "demo",
            "relations": [
                {"fromEntity": a, "toEntity": b, "relationType": "depends_on"} for a, b in pares
            ],
        }),
        encoding="utf-8",
    )


def _entidad(g):
    return [e for e in g["edges"] if e["source"] == "entity_relations"]


def test_ap17_una_entidad_parecida_es_sugerencia(vault):
    _nota(vault, "07_Knowledge/user-service.md", "u", title="User Service")
    _nota(vault, "07_Knowledge/orders.md", "o", title="Orders")
    _relaciones(vault, ("Orders", "UserServce"))
    _, g = _enriquecido(vault)
    [arista] = _entidad(g)
    assert arista["endpoint_resolved"] is False
    assert arista["to"] == "UserServce"
    assert {
        "source": "entity_relations",
        "endpoint": "UserServce",
        "criterion": "similar",
        "candidates": ["07_Knowledge/user-service.md"],
    } in g["suggestions"]


def test_ap17_una_entidad_con_la_misma_clave_es_la_nota(vault):
    _nota(vault, "07_Knowledge/user-service.md", "u", title="User Service")
    _nota(vault, "07_Knowledge/orders.md", "o", title="Orders", aliases="[Pedidos]")
    _relaciones(vault, ("Pedidos", "UserService"))
    _, g = _enriquecido(vault)
    [arista] = _entidad(g)
    assert (arista["from"], arista["to"], arista["endpoint_resolved"]) == (
        "07_Knowledge/orders.md",
        "07_Knowledge/user-service.md",
        True,
    )


def test_ap17_una_entidad_con_dos_notas_es_ambigua(vault):
    _nota(vault, "07_Knowledge/user-service.md", "u", title="U")
    _nota(vault, "11_Code/UserService.md", "u", title="U")
    _nota(vault, "07_Knowledge/orders.md", "o", title="Orders")
    _relaciones(vault, ("Orders", "UserService"))
    _, g = _enriquecido(vault)
    [arista] = _entidad(g)
    assert arista["endpoint_resolved"] is False
    assert {
        "source": "entity_relations",
        "endpoint": "UserService",
        "criterion": "ambiguous",
        "candidates": ["07_Knowledge/user-service.md", "11_Code/UserService.md"],
    } in g["suggestions"]


def test_ap17_una_entidad_por_title_es_sugerencia(vault):
    _nota(vault, "07_Knowledge/svc-01.md", "u", title="Billing Engine")
    _nota(vault, "07_Knowledge/orders.md", "o", title="Orders")
    _relaciones(vault, ("Orders", "Billing Engine"))
    _, g = _enriquecido(vault)
    [arista] = _entidad(g)
    assert arista["endpoint_resolved"] is False
    assert any(
        s["endpoint"] == "Billing Engine" and s["criterion"] == "title" for s in g["suggestions"]
    ), g["suggestions"]
