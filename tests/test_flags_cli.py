"""Un solo lector de `add_argument` (v41.9).

Hasta v41.8 había cinco: el AST de `vault_mcp_catalog.argparse_params` y
cuatro regex. El productor de `tool-spec.json` (`vault_manifest`) y su
validador (`vault_spec_validate`) leían con regex distintas, así que el que
mide se certificaba con su propio criterio (AP-44) y el criterio con dueño
estaba reescrito en cuatro sitios (AP-57). Las regex solo veían el primer
nombre de la llamada y encontraban `add_argument(` dentro de un docstring.

Y el canónico no leía `action=argparse.BooleanOptionalAction`, que no es un
literal: `--reversible` se publicaba por MCP como texto y su `false` no tenía
forma de llegar a la CLI.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "scripts")]

from vault.meta_toolkit import flags_cli  # noqa: E402

FUENTE = '''
"""Ejemplo: `parser.add_argument("--fantasma")` en un docstring no es un flag."""
import argparse
p = argparse.ArgumentParser()
p.add_argument("-o", "--output", required=True, help="dónde")
p.add_argument("--modo", help="texto con required=True dentro")
p.add_argument("--reversible", action=argparse.BooleanOptionalAction, default=True)
p.add_argument("--rapido", action="store_true")
p.add_argument("nota")
'''


def test_el_extractor_lee_el_ast_no_el_texto():
    assert flags_cli.flags_aceptados(FUENTE) == {
        "-o", "--output", "--modo", "--reversible", "--no-reversible", "--rapido"}
    assert flags_cli.obligatorios(FUENTE) == ["--output"]


def test_los_cuatro_lectores_delegan_en_el_extractor_unico(tmp_path):
    import vault_doc_sync
    import vault_manifest
    import vault_spec_memory
    import vault_spec_validate

    assert vault_spec_validate._extract_argparse_flags(FUENTE) == flags_cli.flags_aceptados(FUENTE)
    assert vault_manifest._extract_required_flags(FUENTE) == flags_cli.obligatorios(FUENTE)
    requeridos, opcionales = vault_spec_memory._extract_args(FUENTE)
    assert [a["flag"] for a in requeridos] == ["-o", "nota"]
    assert {a["flag"] for a in opcionales} == {"--modo", "--reversible", "--rapido"}
    script = tmp_path / "ejemplo.py"
    script.write_text(FUENTE, encoding="utf-8")
    assert vault_doc_sync._flags_declarados(script) == {
        "--output", "--modo", "--reversible", "--no-reversible", "--rapido"}


def test_un_negable_se_publica_booleano_con_su_marca():
    catalogo = json.loads((REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    prop = catalogo["tools"]["vault_ai_decision"]["inputSchema"]["properties"]["reversible"]
    assert prop["type"] == "boolean" and prop["x-negable"] is True, prop


@pytest.mark.skipif(shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH")
def test_el_false_de_un_negable_llega_a_la_cli(tmp_path):
    from test_mcp_runner import SesionMCP, _init_vault

    vault = _init_vault(tmp_path / "vault")
    sesion = SesionMCP(vault)
    try:
        alta = json.loads(sesion.llamar("vault_project", {"add": "demo"})["result"]["content"][0]["text"])
        assert alta["ok"] is True, alta
        respuesta = sesion.llamar("vault_ai_decision", {
            "project": "demo", "title": "Borrar la tabla vieja", "decision_type": "architectural",
            "description": "Se borra la tabla vieja tras migrar.",
            "rationale": "Ya nadie la lee y ocupa espacio.", "reversible": False,
        })
    finally:
        sesion.cerrar()
    env = json.loads(respuesta["result"]["content"][0]["text"])
    assert env["ok"] is True, env
    texto = (vault / env["path"]).read_text(encoding="utf-8")
    assert yaml.safe_load(texto.split("---", 2)[1])["reversible"] is False, texto
