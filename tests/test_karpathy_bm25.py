"""Full-text lexical ranking (BM25) over the whole note, stdlib only.

`vault_search` scored title, tags and the 200-character preview: a word in
the fourth paragraph did not exist for it. The index producer now stores term
statistics per note, and `vault_search --ranking bm25` scores them. Measured
with the agent bench before choosing the default (see `RANKING_POR_DEFECTO`).
"""

import json
from pathlib import Path

import pytest

from apoyo import correr_en_proceso, escribir_nota

RELLENO = "\n\n".join(f"Párrafo {i} sobre el despliegue ordinario del servicio." for i in range(6))


@pytest.fixture
def vault(tmp_path):
    import vault_io

    raiz = tmp_path / "vault"
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / sec).mkdir(parents=True)
    escribir_nota(raiz, "07_Knowledge/profunda.md", {"title": "Despliegue"},
                  f"# Despliegue\n\n{RELLENO}\n\nAl final aparece el quetzal migratorio.\n")
    escribir_nota(raiz, "07_Knowledge/otra.md", {"title": "Otra nota"},
                  "# Otra nota\n\nNada que ver con aves.\n")
    previa = vault_io.set_vault_root(raiz)
    import vault_reindex

    assert vault_reindex.vault_reindex()["ok"]
    yield raiz
    vault_io.set_vault_root(previa)


def _filas(raiz: Path) -> dict:
    indice = json.loads((raiz / "99_Index" / "search-index.json").read_text(encoding="utf-8"))
    return {n["path"]: n for n in indice["notes"]}


def test_el_indice_guarda_las_estadisticas_de_terminos_de_la_nota_entera(vault):
    fila = _filas(vault)["07_Knowledge/profunda.md"]

    assert fila["terms"]["quetzal"] == 1
    assert fila["terms"]["despliegue"] >= 2  # title counts too
    assert fila["length"] == sum(fila["terms"].values())


def test_bm25_encuentra_una_palabra_fuera_del_extracto(vault):
    import vault_search

    r = vault_search.vault_search("quetzal migratorio", ranking="bm25")

    assert r["ok"] and r["ranking"] == "bm25", r
    assert [x["path"] for x in r["results"]] == ["07_Knowledge/profunda.md"]


def test_el_ranking_por_pesos_conserva_su_comportamiento(vault):
    import vault_search

    r = vault_search.vault_search("quetzal migratorio", ranking="pesos")

    assert r["ok"] and r["ranking"] == "pesos" and r["results"] == [], r


def test_un_indice_sin_estadisticas_cae_a_pesos_y_lo_dice(vault):
    import vault_search

    destino = vault / "99_Index" / "search-index.json"
    indice = json.loads(destino.read_text(encoding="utf-8"))
    for fila in indice["notes"]:
        fila.pop("terms", None)
        fila.pop("length", None)
    destino.write_text(json.dumps(indice), encoding="utf-8")

    r = vault_search.vault_search("despliegue", ranking="bm25")

    assert r["ok"] and r["ranking"] == "pesos", r
    assert any("vault_reindex" in w for w in r.get("warnings", []))
    assert r["results"], r


def test_un_ranking_desconocido_es_un_error_de_entrada(vault):
    import vault_search

    r = vault_search.vault_search("despliegue", ranking="semantico")
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r


def test_la_cli_acepta_ranking(vault):
    corrida = correr_en_proceso("vault_search", "--query", "quetzal", "--ranking", "bm25",
                                vault=vault)
    assert corrida.codigo == 0 and corrida.envelope["ranking"] == "bm25", corrida.envelope


def test_la_nota_recien_escrita_entra_con_sus_estadisticas(vault):
    import vault_io

    nota = vault / "07_Knowledge" / "nueva.md"
    vault_io.atomic_write_text(nota, "---\ntitle: Nueva\n---\n\n# Nueva\n\nUn ajolote.\n")
    import vault_io as io

    io.update_section_index("07_Knowledge")
    assert _filas(vault)["07_Knowledge/nueva.md"]["terms"]["ajolote"] == 1
