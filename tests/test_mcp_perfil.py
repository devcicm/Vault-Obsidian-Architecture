"""`VAULT_MCP_PERFIL` — el servidor MCP expone a un agente solo su perfil.

Medido el 2026-10-07: por MCP el agente recibía en `tools/list` todas las
tools `runtime` del catálogo, sin nada que le dijera cuáles usa una sesión, y
cada una cuesta su descripción y su esquema en la ventana de contexto. El
perfil `agente` sale de `vault.meta_toolkit.protocolo_de_sesion` y viaja en
`tools-catalog.json` → `perfiles`; el servidor lo aplica si se le pide.

Sin la variable no cambia nada: quien hoy espera el catálogo entero lo sigue
recibiendo. Un perfil desconocido no arranca, porque caer al catálogo entero
sería dar al agente justo lo que su dueño pidió no darle.

Se comprueba con el criterio del consumidor (AP-44): sesión JSON-RPC real.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_mcp_runner import SERVER, SesionMCP, _init_vault

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGO = json.loads(
    (REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
ENV_TABLE = json.loads(
    (REPO_ROOT / "mcp" / "nodejs" / "env-table.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    return _init_vault(tmp_path_factory.mktemp("mcpperfil") / "vault")


def _nombres(sesion) -> set:
    return {t["name"] for t in sesion._pedir("tools/list", {})["result"]["tools"]}


def _envelope(respuesta) -> dict:
    return json.loads(respuesta["result"]["content"][0]["text"])


def test_la_variable_esta_declarada_en_el_registro_de_entorno():
    nombres = {v["name"] for v in ENV_TABLE["variables"]}
    assert "VAULT_MCP_PERFIL" in nombres


def test_sin_perfil_tools_list_no_cambia(vault):
    s = SesionMCP(vault, {"VAULT_MCP_PERFIL": ""})
    try:
        esperadas = {n for n, t in CATALOGO["tools"].items()
                     if t.get("exposed_via_mcp") is not False}
        assert _nombres(s) == esperadas
    finally:
        s.cerrar()


def test_con_perfil_agente_tools_list_es_el_perfil(vault):
    s = SesionMCP(vault, {"VAULT_MCP_PERFIL": "agente"})
    try:
        assert _nombres(s) == set(CATALOGO["perfiles"]["agente"])
    finally:
        s.cerrar()


def test_con_perfil_una_tool_fuera_se_rechaza_sin_ejecutarse(vault):
    fuera = "vault_tags"
    assert fuera not in CATALOGO["perfiles"]["agente"]
    s = SesionMCP(vault, {"VAULT_MCP_PERFIL": "agente"})
    try:
        env = _envelope(s.llamar(fuera, {}))
        assert env["error_code"] == "tool_not_found", env
        assert "agente" in env["message"], env
        dentro = _envelope(s.llamar("vault_search", {"query": "index"}))
        assert dentro.get("error_code") != "tool_not_found", dentro
    finally:
        s.cerrar()


def test_un_perfil_desconocido_no_arranca(vault):
    env = {**os.environ, "VAULT_ROOT": str(vault), "VAULT_MCP_PERFIL": "no-existe"}
    r = subprocess.run(["node", str(SERVER)], input="", capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env=env, cwd=str(REPO_ROOT), timeout=60)
    assert r.returncode != 0
    assert "no-existe" in r.stderr and "agente" in r.stderr, r.stderr
