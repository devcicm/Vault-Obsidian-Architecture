"""Los pesos del context pack se publican, y el intento se registra.

Propuesta `compact-agent-memory-weights`: los pesos del rerank (0,45 léxico /
0,30 grafo / 0,15 recencia / 0,10 CIA) eran **constantes de implementación,
no pesos medidos**, y el consumidor no los veía. Y el briefing no sabía con
qué propósito se le pedía.

Lo que se entrega, con la honestidad de la propuesta:

- los pesos se **declaran** en un registro y viajan en el envelope junto a
  la frase que dice qué son (una decisión de diseño, no una medición);
- el **intento** de la consulta se registra en el envelope. No reordena:
  cambiar el orden sin medir es exactamente lo que la propuesta critica.
"""

from __future__ import annotations

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_context_pack
import vault_io


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for carpeta in ("00_System", "07_Knowledge"):
        (raiz / carpeta).mkdir(parents=True)
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota de prueba\ntags: [prueba]\nstatus: draft\n---\n\n"
        "Contenido sobre el tema de la consulta de prueba.\n",
        encoding="utf-8")
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def test_los_pesos_suman_uno_y_estan_declarados():
    pesos = vault_context_pack.PESOS_RERANK
    assert abs(sum(pesos.values()) - 1.0) < 1e-9, pesos
    assert set(pesos) == {"lexical", "graph", "recency", "cia"}, pesos


def test_el_envelope_publica_los_pesos_y_su_origen(vault):
    res = vault_context_pack.vault_context_pack("consulta de prueba")
    assert res.get("ok"), res
    assert res.get("weights") == vault_context_pack.PESOS_RERANK, res.get("weights")
    assert "declarados" in res.get("weights_origen", "")


def test_el_intento_se_registra_en_el_envelope(vault):
    res = vault_context_pack.vault_context_pack("consulta de prueba", intento="revisar")
    assert res.get("ok"), res
    assert res.get("intento") == "revisar", res.get("intento")
    assert "no reordena" in res.get("intento_nota", "")


def test_un_intento_inventado_se_rechaza(vault):
    res = vault_context_pack.vault_context_pack("consulta", intento="adivinar")
    assert res.get("ok") is False, res
    assert res.get("error_code") == "INVALID_INPUT", res


def test_los_intentos_estan_declarados():
    assert vault_context_pack.INTENTOS == (
        "explorar", "documentar", "cambiar", "depurar", "revisar")
    import vault_grafo_import as gi

    fuente = gi.codigo_de(REPO_ROOT / "scripts" / "vault_context_pack.py").read_text(
        encoding="utf-8")
    assert "compact-agent-memory-weights" in fuente, (
        "el registro de pesos debe citar la propuesta que lo motiva")
