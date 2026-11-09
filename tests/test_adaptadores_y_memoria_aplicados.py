"""Los adaptadores llevan la politica real, y la memoria declara su alcance.

La revision independiente (2026-11-09) senalo que los adaptadores de
politica y la memoria para agentes **tenian avances, pero su aplicacion y
cobertura completas estaban sin verificar**. Aqui se verifica la aplicacion:
el fichero generado lleva las preferencias que el vault declara (no una
resumen generico) y las reglas, y la memoria declara lo que es y lo que no.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_context_pack
import vault_io
import vault_preferences


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for carpeta in ("00_System", "07_Knowledge", "17_Preferences"):
        (raiz / carpeta).mkdir(parents=True)
    (raiz / "17_Preferences" / "workflow" ).mkdir(parents=True, exist_ok=True)
    (raiz / "17_Preferences" / "workflow" / "regla.md").write_text(
        "---\ntitle: Regla de trabajo\ntype: preference\nstatus: active\n"
        "strength: must\ncategory: workflow\n"
        "statement: No mover tools entre repositorios sin peticion explicita "
        "del dueno.\n---\n\nLa regla.\n",
        encoding="utf-8")
    (raiz / "00_System" / "reglas.json").write_text(
        json.dumps({"no_borrar": ["19_Audits"]}), encoding="utf-8")
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\ntype: note\nstatus: draft\ntags: [x]\n---\n\n"
        "Contenido sobre el tema de la consulta, con texto suficiente.\n",
        encoding="utf-8")
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def test_el_adaptador_lleva_la_preferencia_real_del_vault(vault, tmp_path):
    """No basta con que el fichero exista: tiene que llevar la politica."""
    destino = tmp_path / "proyecto"
    destino.mkdir()

    res = vault_preferences.vault_preferences_adapters(str(destino))

    assert res.get("ok"), res
    cuerpo = (destino / "AGENTS.md").read_text(encoding="utf-8")
    # La preferencia `must` del vault, con su enunciado.
    assert "No mover tools entre repositorios" in cuerpo, cuerpo[:600]
    # Y la regla de no borrar.
    assert "19_Audits" in cuerpo, cuerpo[:600]
    # Y lo que el fichero es y lo que no es.
    assert "no enforcing" in cuerpo.lower()
    assert "frontera de mutaci" in cuerpo


def test_los_cuatro_clientes_reciben_lo_mismo(vault, tmp_path):
    """Los cuatro ficheros de cliente llevan la misma politica."""
    destino = tmp_path / "proyecto2"
    destino.mkdir()
    vault_preferences.vault_preferences_adapters(str(destino))

    for nombre in ("AGENTS.md", "CLAUDE.md", "GEMINI.md",
                   ".github/copilot-instructions.md"):
        ruta = destino / nombre
        assert ruta.is_file(), nombre
        cuerpo = ruta.read_text(encoding="utf-8")
        assert "No mover tools entre repositorios" in cuerpo, nombre
        assert "19_Audits" in cuerpo, nombre


def test_la_memoria_declara_su_alcance_y_su_intento(vault):
    """La memoria dice que pesos usa y que el intento no reordena."""
    res = vault_context_pack.vault_context_pack(
        "consulta sobre el tema", intento="documentar")
    assert res.get("ok"), res
    assert res.get("weights"), res
    assert "declarados" in res.get("weights_origen", "")
    assert res.get("intento") == "documentar"
    assert "no reordena" in res.get("intento_nota", "")


def test_el_contexto_deja_ver_las_restricciones_del_dueno(vault):
    """Una preferencia `must` tiene que aparecer en el paquete de contexto.

    Si no, el «contexto estable» no lo seria: el agente recibiria el
    contexto sin la restriccion que el dueno declaro.
    """
    res = vault_context_pack.vault_context_pack(
        "consulta sobre el tema", include_preferences=True)
    assert res.get("ok"), res
    assert res.get("preferences_included", 0) >= 1, res
    contexto = res.get("context") or ""
    assert "No mover tools entre repositorios" in contexto, contexto[:600]


def test_el_limite_de_la_memoria_esta_publicado():
    """El alcance del context pack, en su propio codigo (AP-57: un criterio
    con un solo dueno)."""
    import vault_grafo_import as gi

    fuente = gi.codigo_de(REPO_ROOT / "scripts" / "vault_context_pack.py").read_text(
        encoding="utf-8")
    assert "compact-agent-memory-weights" in fuente, (
        "el registro de pesos debe citar la propuesta que lo motiva")
