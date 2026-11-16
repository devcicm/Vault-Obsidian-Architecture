"""Evaluación etiquetada del context pack con índice y búsqueda reales.

Los fixtures viven en el sandbox de un clon aislado; no evalúan semántica ni
autoridad entre notas contradictorias y no calibran los pesos de reranking.
"""

import pytest

import vault_context_pack as pack
import vault_io
import vault_reindex
import vault_search


@pytest.fixture(scope="module")
def corpus_real():
    raiz = vault_io.get_vault_root()
    assert raiz.name == "vault-sandbox"
    carpeta = raiz / "07_Knowledge" / "evaluacion-contexto-real"
    carpeta.mkdir(parents=True, exist_ok=True)
    notas = {
        "a-favor.md": ("Zxqrescate postura favorable", "zxqrescate acepta la propuesta. " * 100),
        "en-contra.md": ("Zxqrescate postura contraria", "zxqrescate rechaza la propuesta."),
        "irrelevante.md": ("Tema distinto", "Texto ajeno a la consulta."),
    }
    for nombre, (titulo, cuerpo) in notas.items():
        (carpeta / nombre).write_text(
            f"---\ntitle: {titulo}\ntype: note\nstatus: active\ntags: [evaluacion]\n---\n\n{cuerpo}\n",
            encoding="utf-8",
        )
    preferencias = raiz / "17_Preferences" / "evaluacion-contexto-real"
    preferencias.mkdir(parents=True, exist_ok=True)
    (preferencias / "regla.md").write_text(
        "---\ntitle: Restriccion de evaluacion\ntype: preference\nstatus: active\n"
        "strength: must\ncategory: workflow\n"
        "statement: Conservar la evidencia zxqrescate.\n---\n\nRegla.\n",
        encoding="utf-8",
    )
    resultado = vault_reindex.vault_reindex()
    assert resultado.get("ok"), resultado
    base = "07_Knowledge/evaluacion-contexto-real/"
    return {base + "a-favor.md", base + "en-contra.md"}


def test_recuperacion_real_conserva_las_dos_posturas(corpus_real):
    resultado = pack.vault_context_pack("zxqrescate", budget_tokens=3000,
                                        top_k=10, excerpt_tokens=20,
                                        include_preferences=False)
    assert resultado["ok"], resultado
    incluidas = {nota["path"] for nota in resultado["included"]}
    assert corpus_real <= incluidas
    assert not any("irrelevante.md" in ruta for ruta in incluidas)
    assert len(corpus_real & incluidas) / len(corpus_real) == 1.0
    assert any(nota["truncated"] for nota in resultado["included"]
               if nota["path"].endswith("a-favor.md"))
    assert resultado["tokens"]["used"] <= resultado["tokens"]["budget"]


def test_consulta_real_sin_coincidencias_no_inventa_resultados(corpus_real):
    resultado = pack.vault_context_pack("zxyimposiblequenoexiste",
                                        include_preferences=False)
    assert resultado["ok"], resultado
    assert resultado["included"] == []
    assert any("ninguna nota" in aviso for aviso in resultado["warnings"])


def test_preferencia_obligatoria_real_llega_al_contexto(corpus_real):
    resultado = pack.vault_context_pack("zxqrescate", budget_tokens=3000,
                                        include_preferences=True)
    assert resultado["ok"], resultado
    assert resultado["preferences_included"] >= 1
    assert "Conservar la evidencia zxqrescate" in resultado["context"]
    assert resultado["tokens"]["used"] <= resultado["tokens"]["budget"]


def test_preferencia_obligatoria_no_desborda_el_presupuesto(corpus_real):
    resultado = pack.vault_context_pack("zxqrescate", budget_tokens=10,
                                        include_preferences=True)
    assert not resultado["ok"], resultado
    assert resultado["error_code"] == "INVALID_BUDGET"
    assert "context" not in resultado


def test_limite_top_k_declara_omisiones_reales(corpus_real):
    resultado = pack.vault_context_pack("zxqrescate", budget_tokens=3000,
                                        top_k=1, include_preferences=False)
    incluidas = {nota["path"] for nota in resultado["included"]}
    omitidas = {nota["path"] for nota in resultado["excluded"]
                if nota["reason"] == "fuera del top-k"}
    assert len(corpus_real & incluidas) == 1
    assert len(corpus_real & omitidas) == 1


def test_indice_ausente_informa_error_de_busqueda(corpus_real, monkeypatch):
    inexistente = vault_io.get_vault_root() / "99_Index" / "indice-inexistente-test.json"
    assert not inexistente.exists()
    monkeypatch.setattr(vault_search, "_index_file", lambda: inexistente)
    resultado = pack.vault_context_pack("zxqrescate", include_preferences=False)
    assert resultado["ok"], resultado
    assert resultado["included"] == []
    assert any("búsqueda léxica" in aviso for aviso in resultado["warnings"])


def test_error_en_reintento_de_busqueda_no_se_oculta(corpus_real, monkeypatch):
    parsear = pack.vault_query_parse

    def con_seccion(query):
        resultado = parsear(query)
        resultado["structured"]["sections_named"] = ["11_Code"]
        return resultado

    def buscar(_query, folder=None):
        if folder:
            return {"ok": True, "results": []}
        return {"ok": False, "error_code": "INDEX_NOT_FOUND",
                "message": r"fallo en C:\private-fixture\index.json", "results": []}

    monkeypatch.setattr(pack, "vault_query_parse", con_seccion)
    monkeypatch.setattr(pack, "vault_search", buscar)
    resultado = pack.vault_context_pack("zxqrescate", include_preferences=False)
    assert resultado["ok"], resultado
    assert any("INDEX_NOT_FOUND" in aviso for aviso in resultado["warnings"])
    assert any("vault_reindex" in aviso for aviso in resultado["warnings"])
    assert all("private-fixture" not in aviso for aviso in resultado["warnings"])


def test_busqueda_incompleta_se_declara_en_el_contexto(corpus_real, monkeypatch):
    monkeypatch.setattr(pack, "vault_search", lambda *_a, **_k: {
        "ok": True, "results": [], "incomplete": True, "skipped": ["nota ilegible"]})
    resultado = pack.vault_context_pack("zxqrescate", include_preferences=False)
    assert resultado["ok"], resultado
    assert any("incomplet" in aviso.lower() for aviso in resultado["warnings"])


def test_indice_desactualizado_se_declara_en_el_contexto(corpus_real):
    raiz = vault_io.get_vault_root()
    nota = raiz / "07_Knowledge" / "evaluacion-contexto-real" / "nueva-desfase.md"
    nota.write_text("---\ntitle: Zxqrescate nueva\ntype: note\n---\n\nzxqrescate", encoding="utf-8")
    try:
        assert vault_reindex.index_coherence()["status"] == "index_stale"
        resultado = pack.vault_context_pack("zxqrescate", include_preferences=False)
        assert resultado["ok"], resultado
        assert any("vault_reindex" in aviso for aviso in resultado["warnings"])
    finally:
        nota.unlink(missing_ok=True)


def test_error_al_verificar_indice_no_expone_rutas(corpus_real, monkeypatch):
    def fallar():
        raise OSError("C:/private-fixture/index.json")

    monkeypatch.setattr(pack, "index_coherence", fallar)
    resultado = pack.vault_context_pack("zxqrescate", include_preferences=False)
    assert resultado["ok"]
    assert any("vault_reindex" in aviso for aviso in resultado["warnings"])
    assert all("private-fixture" not in aviso for aviso in resultado["warnings"])


def test_indice_con_nota_eliminada_se_declara_en_el_contexto(corpus_real):
    raiz = vault_io.get_vault_root()
    nota = raiz / "07_Knowledge" / "evaluacion-contexto-real" / "en-contra.md"
    contenido = nota.read_bytes()
    nota.unlink()
    try:
        assert vault_reindex.index_coherence()["status"] == "index_stale"
        resultado = pack.vault_context_pack("zxqrescate", include_preferences=False)
        assert resultado["ok"], resultado
        assert any("vault_reindex" in aviso for aviso in resultado["warnings"])
    finally:
        nota.write_bytes(contenido)


def test_busqueda_en_vivo_no_comprueba_indice(corpus_real, monkeypatch):
    monkeypatch.setattr(pack, "vault_search", lambda *_a, **_k: {
        "ok": True, "source": "live_visible_markdown", "results": []})

    def no_debe_llamarse():
        pytest.fail("La búsqueda en vivo no utiliza el índice")

    monkeypatch.setattr(pack, "index_coherence", no_debe_llamarse)
    assert pack.vault_context_pack("zxqrescate", include_preferences=False)["ok"]
