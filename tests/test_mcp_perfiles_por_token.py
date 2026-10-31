"""A-13 — cada token del transporte HTTP/SSE abre un perfil.

Hasta v41.25 el servidor aceptaba un único Bearer: quien lo tenía llamaba a
toda tool, incluidas `vault_delete` y `vault_standard_upgrade`. Ahora
`VAULT_MCP_TOKENS=lector:<t>,operador:<t>` declara varios, y `lector` solo ve y
llama a las tools sin side effects. El perfil de cada tool no lo decide el
`.mjs`: es `perfil_minimo`, derivado en `vault_mcp_catalog` de `side_effects`.

Se comprueba con el criterio del consumidor (AP-44): el servidor real, por
HTTP, desde fuera.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_mcp_http_seguridad import SERVER, Servidor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mcp_catalog  # noqa: E402

LECTOR = "lector-" + "l" * 32
OPERADOR = "operador-" + "o" * 32
LEGADO = "legado-" + "g" * 32


# --- derivación, sin servidor -------------------------------------------------

def test_perfil_minimo_sale_de_side_effects():
    assert vault_mcp_catalog.perfil_minimo({"side_effects": []}) == "lector"
    assert vault_mcp_catalog.perfil_minimo({}) == "lector"
    assert vault_mcp_catalog.perfil_minimo({"side_effects": ["writes_notes"]}) == "operador"


def test_la_pasarela_publica_el_perfil_de_cada_tool():
    datos = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    assert datos["perfiles_de_token"] == list(vault_mcp_catalog.PERFILES_DE_TOKEN)
    for nombre, tool in vault_mcp_catalog.TOOLS_CATALOG.items():
        assert datos["tools"][nombre]["perfil_minimo"] == vault_mcp_catalog.perfil_minimo(tool), nombre
    assert datos["tools"]["vault_delete"]["perfil_minimo"] == "operador"
    assert datos["tools"]["vault_read"]["perfil_minimo"] == "lector"


@pytest.mark.parametrize("editar, diff", [
    (lambda d: d["tools"]["vault_delete"].update(perfil_minimo="lector"),
     "vault_delete: perfil_minimo differs"),
    (lambda d: d.update(perfiles_de_token=["lector"]), "perfiles_de_token divergen"),
])
def test_check_sync_ve_un_perfil_editado_a_mano(tmp_path, editar, diff):
    datos = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    editar(datos)
    copia = tmp_path / "tools-catalog.json"
    copia.write_text(json.dumps(datos), encoding="utf-8")
    resultado = vault_mcp_catalog.check_sync(str(copia))
    assert not resultado["ok"]
    assert any(diff in d for d in resultado["diffs"]), resultado["diffs"]


# --- el servidor --------------------------------------------------------------

@pytest.fixture
def servidor(tmp_path):
    vault = tmp_path / "vault"
    for s in ("00_System", "07_Knowledge"):
        (vault / s).mkdir(parents=True)
    srv = Servidor(vault, token=LEGADO, tokens=f"lector:{LECTOR},operador:{OPERADOR}")
    yield srv
    srv.cerrar()


def _rpc(srv, token, sid, cuerpo):
    _, r = srv.pedir("POST", "/message",
                     {"Authorization": f"Bearer {token}", "X-MCP-Session": sid}, cuerpo)
    texto = r.read().decode()
    return r.status, (json.loads(texto) if texto else None)


def _sesion(srv, token):
    c, r, sid = srv.abrir_sse(token)
    _rpc(srv, token, sid, {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1"}}})
    _rpc(srv, token, sid, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    return c, sid


def _nombres(srv, token, sid):
    status, resp = _rpc(srv, token, sid, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert status == 200, resp
    return {t["name"] for t in resp["result"]["tools"]}


def test_lector_solo_ve_las_tools_sin_side_effects(servidor):
    c, sid = _sesion(servidor, LECTOR)
    nombres = _nombres(servidor, LECTOR, sid)
    c.close()
    assert "vault_read" in nombres
    assert "vault_delete" not in nombres and "vault_write" not in nombres
    for n in nombres:
        tool = vault_mcp_catalog.TOOLS_CATALOG.get(n)
        assert tool is None or vault_mcp_catalog.perfil_minimo(tool) == "lector", n


def test_operador_y_el_token_de_siempre_lo_ven_todo(servidor):
    for token in (OPERADOR, LEGADO):
        c, sid = _sesion(servidor, token)
        nombres = _nombres(servidor, token, sid)
        c.close()
        assert {"vault_read", "vault_delete", "vault_write"} <= nombres, token


def test_lector_no_ejecuta_lo_que_no_ve(servidor):
    c, sid = _sesion(servidor, LECTOR)
    status, resp = _rpc(servidor, LECTOR, sid, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "vault_delete", "arguments": {}}})
    c.close()
    assert status == 200
    resultado = resp["result"]
    assert resultado.get("isError") is True
    texto = resultado["content"][0]["text"]
    assert "tool_not_found" in texto and "operador" in texto


def test_una_sesion_no_se_habla_con_otro_token(servidor):
    c, sid = _sesion(servidor, OPERADOR)
    status, _ = _rpc(servidor, LECTOR, sid, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    c.close()
    assert status == 403


def test_un_perfil_desconocido_no_arranca(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="VAULT_MCP_TOKENS"):
        Servidor(vault, token=None, tokens=f"admin:{LECTOR}").cerrar()


def test_el_servidor_no_nombra_ningun_perfil():
    """El `.mjs` no copia la lista: la lee de la pasarela (AP-57)."""
    fuente = SERVER.read_text(encoding="utf-8")
    assert '"lector"' not in fuente and "'lector'" not in fuente
    assert subprocess.run(["node", "--check", str(SERVER)], capture_output=True).returncode == 0
