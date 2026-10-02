"""AP-47: el grafo de wikilinks se refresca nota a nota en cada escritura.

`graph.json` solo lo regeneraba `vault_graph` entero: una nota escrita por
`vault_write`, `vault_ingest` o cualquier `*_save` no existía para
`vault_subgraph` hasta la siguiente reconstrucción, y `_desfase` lo declaraba
pero no lo resolvía. Ahora el gancho del write path del kernel la pone en el
grafo —nodo, aristas salientes y lo que su nombre resuelve en las demás— sin
leer más nota que la escrita: los nodos guardan `aliases` y `links`, y con eso
la resolución se repite en memoria.

La invariante que importa es la equivalencia: lo que deja el refresco es lo que
dejaría una reconstrucción completa. Si divergen, hay dos criterios de grafo.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402


def _escribir(raiz: Path, rel: str, texto: str) -> None:
    ruta = raiz / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    vault_io.atomic_write_text(ruta, texto)


def _grafo(raiz: Path) -> dict:
    return json.loads((raiz / "99_Index" / "graph.json").read_text(encoding="utf-8"))


def _comparable(g: dict) -> dict:
    return {
        "nodes": g["nodes"],
        "edges": sorted(json.dumps(e, sort_keys=True) for e in g["edges"]),
        "orphans": sorted(json.dumps(o, sort_keys=True) for o in g["orphans"]),
        "brokenLinks": sorted(json.dumps(b, sort_keys=True) for b in g["brokenLinks"]),
        "ambiguousLinks": sorted(json.dumps(a, sort_keys=True) for a in g["ambiguousLinks"]),
        "nameCollisions": g["nameCollisions"],
        "stats": g["stats"],
    }


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "07_Knowledge", "11_Code", "99_Index"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    (tmp_path / "07_Knowledge" / "hub.md").write_text(
        "---\ntitle: Hub\n---\n\n[[cache]] [[Redis]] [[overview]]\n", encoding="utf-8"
    )
    (tmp_path / "07_Knowledge" / "overview.md").write_text("---\ntitle: O\n---\n", encoding="utf-8")
    vault_io.set_vault_root(tmp_path)
    import vault_graph

    vault_graph.vault_graph()
    return tmp_path


def _rotos_del_hub(g: dict) -> list:
    # Los `index.md` generados enlazan a las notas hub, y su resolución no es
    # lo que se prueba aquí: solo cuentan los enlaces de la nota de partida.
    return [b["link"] for b in g["brokenLinks"] if b["from"] == "07_Knowledge/hub.md"]


def test_la_nota_escrita_entra_en_el_grafo_sin_reconstruir(vault):
    assert _rotos_del_hub(_grafo(vault)) == ["cache", "Redis"]
    _escribir(vault, "07_Knowledge/cache.md", "---\ntitle: Cache\naliases: [Redis]\n---\n\n[[hub]]\n")
    g = _grafo(vault)
    assert g["nodes"]["07_Knowledge/cache.md"]["aliases"] == ["Redis"]
    pares = sorted((e["from"], e["to"]) for e in g["edges"])
    # Las salientes de la nota nueva y las entrantes que su nombre y su alias
    # resuelven ahora en otra nota, que no se ha vuelto a leer.
    assert ("07_Knowledge/cache.md", "07_Knowledge/hub.md") in pares
    assert ("07_Knowledge/hub.md", "07_Knowledge/cache.md") in pares
    assert _rotos_del_hub(g) == []
    [arista] = [
        e for e in g["edges"]
        if (e["from"], e["to"]) == ("07_Knowledge/hub.md", "07_Knowledge/cache.md")
    ]
    assert arista["occurrences"] == 2


def test_una_nota_homonima_vuelve_ambiguo_un_enlace(vault):
    _escribir(vault, "11_Code/overview.md", "---\ntitle: Otro\n---\n")
    g = _grafo(vault)
    assert ("07_Knowledge/hub.md", "07_Knowledge/overview.md") not in {
        (e["from"], e["to"]) for e in g["edges"]
    }
    assert [a for a in g["ambiguousLinks"] if a["from"] == "07_Knowledge/hub.md"] == [{
        "from": "07_Knowledge/hub.md",
        "link": "overview",
        "candidates": ["07_Knowledge/overview.md", "11_Code/overview.md"],
    }]


def test_el_refresco_deja_lo_mismo_que_la_reconstruccion(vault):
    import vault_graph

    _escribir(vault, "07_Knowledge/cache.md", "---\ntitle: Cache\naliases: [Redis]\n---\n\n[[hub]]\n")
    _escribir(vault, "11_Code/overview.md", "---\ntitle: Otro\ntags:\n  - api\n---\n\n[[nada]]\n")
    _escribir(vault, "00_System/notas.md", "---\ntitle: Sistema\n---\n\n[[cache]]\n")
    _escribir(vault, "07_Knowledge/cache.md", "---\ntitle: Cache 2\n---\n\n[[11_Code/overview]]\n")
    refrescado = _comparable(_grafo(vault))
    vault_graph.vault_graph()
    assert refrescado == _comparable(_grafo(vault))


def test_un_grafo_sin_aliases_no_se_refresca_a_ciegas(vault):
    """Un `graph.json` anterior no guarda `aliases`: resolver con él perdería
    los alias de las notas que no se leen. Se declara, no se adivina (AP-37)."""
    ruta = vault / "99_Index" / "graph.json"
    viejo = _grafo(vault)
    for nodo in viejo["nodes"].values():
        nodo.pop("aliases")
    ruta.write_text(json.dumps(viejo), encoding="utf-8")
    from vault_graph import refrescar_nota_en_grafo

    _escribir(vault, "07_Knowledge/cache.md", "---\ntitle: Cache\n---\n")
    assert json.loads(ruta.read_text(encoding="utf-8")) == viejo
    r = refrescar_nota_en_grafo(vault / "07_Knowledge" / "cache.md")
    assert (r["refreshed"], r["reason"]) == (False, "graph_without_aliases")
    assert "vault_graph" in r["hint"]


def test_sin_grafo_no_se_crea_uno(tmp_path):
    (tmp_path / "07_Knowledge").mkdir(parents=True)
    vault_io.set_vault_root(tmp_path)
    _escribir(tmp_path, "07_Knowledge/a.md", "---\ntitle: A\n---\n")
    assert not (tmp_path / "99_Index" / "graph.json").exists()


def test_fuera_de_una_seccion_no_es_nodo(vault):
    antes = _grafo(vault)
    _escribir(vault, "suelta.md", "---\ntitle: S\n---\n\n[[hub]]\n")
    assert _grafo(vault) == antes


def test_el_gancho_del_grafo_esta_declarado_y_no_cuenta_como_cruce():
    """El kernel llama al dominio de Grafo en cada escritura: es un gancho, con
    motivo y presupuesto, no un cruce escondido en la baseline genérica."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from vault_arch import GANCHOS_DEL_KERNEL, PRESUPUESTO_DE_GANCHOS, cruces

    clave = ("vault_io", "vault/grafo")
    assert "AP-47" in GANCHOS_DEL_KERNEL.get(clave, "")
    assert clave in PRESUPUESTO_DE_GANCHOS
    assert clave not in {(c["from"], c["to"]) for c in cruces()}


def test_un_grafo_ilegible_no_se_pisa_y_se_nombra_su_causa(vault):
    """Ilegible no es ausente: refrescar sobre un grafo vacío dejaría uno con
    una sola nota encima del que había. El dominio nombra la causa y la tool
    escribe el envelope (AP-52)."""
    ruta = vault / "99_Index" / "graph.json"
    ruta.write_text("{ roto", encoding="utf-8")
    _escribir(vault, "07_Knowledge/cache.md", "---\ntitle: Cache\n---\n")
    assert ruta.read_text(encoding="utf-8") == "{ roto"
    from vault_graph import refrescar_nota_en_grafo

    r = refrescar_nota_en_grafo(vault / "07_Knowledge" / "cache.md")
    assert r["ok"] is False
    assert (r["error_code"], r["causa"]) == ("DATA_FILE_CORRUPT", "INDICE_ILEGIBLE")
    assert "vault_graph" in r["hint"]
