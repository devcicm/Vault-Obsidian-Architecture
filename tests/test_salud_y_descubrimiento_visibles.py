"""4.7 — la salud se publica con sus señales, y toda nota de un vault
aislada es descubrible.

El paper de la re-auditoría pedía dos cosas del lado de la salud y la
búsqueda:

1. **El peso de cada señal, sus falsos positivos y la evidencia deben ser
   visibles.** Hoy el envelope ya publica `healthProfile` (por familia:
   salud, penalización, tope, si tocó fondo y qué significa) y `penalties`
   (por señal: id, familia, norma, cuántas veces, cuánto restó y con qué
   tope). Lo que faltaba era que **nadie lo volviera a reducir a un número**:
   esto lo congela.
2. **Descubrimiento con vaults y procesos aislados.** La búsqueda en vivo
   puntúa sobre el markdown visible; aquí se prueba que en un vault
   construido a mano —con notas en la raíz, en carpetas y con etiquetas—
   **todas** las notas son alcanzables, no solo las que están en el índice.

Lo que la salud NO promete (y por eso el score no es un certificado): un
número no demuestra que los datos sean verdaderos, útiles o completos. Lo
que hace es decir **de qué está hecho** y cuánto resta cada señal.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_io  # noqa: E402
import vault_search  # noqa: E402


# ── La salud se publica con sus señales ───────────────────────────────────────


def test_el_score_publica_sus_senales_y_sus_pesos():
    """Un número solo no dice de qué está hecho: el envelope lo desglosa."""
    from vault_audit import PENALIZACIONES, calcular_salud

    unidades = {PENALIZACIONES[0]["id"]: 3}
    salud = calcular_salud(unidades)

    assert "healthScore" in salud and "healthIndex" in salud
    perfil = salud["healthProfile"]
    assert perfil, "no hay perfil por familia"
    for familia, datos in perfil.items():
        assert {"health", "penalty", "cap", "saturated", "means"} <= set(datos), (familia, datos)
        assert datos["means"], f"la familia {familia} no dice qué significa"

    detalle = salud["penalties"]
    assert detalle, "las señales aplicadas no se publican"
    for p in detalle:
        assert {"id", "familia", "norm_code", "count", "penalty", "cap"} <= set(p), p
        # La penalización no puede pasar del tope: si lo pasara, el perfil
        # dejaría de ser una cuenta.
        assert p["penalty"] <= p["cap"], p


def test_una_senal_que_no_aparece_no_inventa_penalizacion():
    """Lo que no se detecta no se penaliza: el detalle lo dice."""
    from vault_audit import calcular_salud

    salud = calcular_salud({})
    assert salud["penalties"] == []
    assert salud["healthScore"] == 100


# ── Descubrimiento en un vault aislado ───────────────────────────────────────


@pytest.fixture
def vault_aislado(tmp_path):
    """Un vault a mano: notas en la raíz, en carpetas y con etiquetas."""
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "11_Code").mkdir(parents=True)
    (raiz / "00_System").mkdir(parents=True)

    (raiz / "RAIZ.md").write_text(
        "---\ntitle: raiz\ntags: [manual]\n---\n\nUna nota en la raiz del vault.\n",
        encoding="utf-8")
    (raiz / "07_Knowledge" / "concepto.md").write_text(
        "---\ntitle: concepto\ntags: [sabiduria]\n---\n\nSobre el concepto.\n",
        encoding="utf-8")
    (raiz / "11_Code" / "modulo.md").write_text(
        "---\ntitle: modulo\ntags: [codigo]\n---\n\nUn modulo de codigo.\n",
        encoding="utf-8")
    # Sin frontmatter: la búsqueda en vivo también tiene que encontrarla.
    (raiz / "11_Code" / "sin-meta.md").write_text("Una nota sin frontmatter.\n",
                                                  encoding="utf-8")
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def test_toda_nota_de_un_vault_aislado_es_descubrible(vault_aislado, monkeypatch):
    """Descubrimiento, no búsqueda: toda nota del vault tiene que salir.

    La propiedad no es que una consulta cualquiera las encuentre todas —eso
    sería del score, no del inventario—, sino que **cada nota es alcanzable**
    por una consulta que la nombra. Y que la búsqueda en vivo es la que
    responde (`source`), no el índice.
    """
    monkeypatch.setenv("VAULT_MCP_LIVE_SEARCH", "1")
    monkeypatch.setattr(vault_search, "_raiz", lambda: vault_aislado)
    monkeypatch.setattr(vault_search, "_index_file",
                        lambda: vault_aislado / "99_Index" / "search-index.json")

    esperados = {
        "raiz": "RAIZ.md",
        "concepto": "07_Knowledge/concepto.md",
        "modulo": "11_Code/modulo.md",
        "sin frontmatter": "11_Code/sin-meta.md",
    }
    for consulta, ruta in esperados.items():
        res = vault_search.vault_search(consulta)
        assert res["ok"], res
        assert res.get("source") == "live_visible_markdown", res
        rutas = [r["path"] for r in res["results"]]
        assert ruta in rutas, f"la nota {ruta} no salió buscando «{consulta}» ({rutas})"


def test_la_busqueda_por_indice_no_inventa_notas(vault_aislado, monkeypatch):
    """Sin el modo vivo, la búsqueda usa el índice: y el índice no está."""
    monkeypatch.delenv("VAULT_MCP_LIVE_SEARCH", raising=False)
    monkeypatch.setattr(vault_search, "_raiz", lambda: vault_aislado)
    monkeypatch.setattr(vault_search, "_index_file",
                        lambda: vault_aislado / "99_Index" / "search-index.json")

    res = vault_search.vault_search("raiz")
    # Sin índice, la búsqueda no puede afirmar nada: se declara.
    assert res["ok"] is False or res["results"] == [], res
