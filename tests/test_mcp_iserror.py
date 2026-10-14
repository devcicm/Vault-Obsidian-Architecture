"""El servidor MCP no marcaba `isError` cuando la tool fallaba (AP-44).

Un `tools/call` que ejecutaba la tool y recibía `{"ok": false, "code": ...}`
—nota inexistente, ruta inválida— respondía con el envelope en `content` y sin
`isError`. El criterio del consumidor es el del protocolo: un cliente MCP decide
si la llamada falló mirando `isError`, no abriendo el texto. Para él, leer una
nota que no existe era un éxito. Solo `formatToolError` —los fallos que el
propio servidor detecta antes de lanzar la tool— lo marcaba.

Lo encontró una sesión de agente consumidor por stdio el 2026-10-14.
"""

import pytest

from test_mcp_instalado import _entorno, _instalacion, _sesion, _vault, requiere_node


def _llamar(tmp_path, nombre, argumentos):
    site = tmp_path / "site"
    servidor = _instalacion(site)
    vault = _vault(tmp_path / "vault")
    rc, resp, err = _sesion(servidor, vault, _entorno(site, VAULT_ROOT=str(vault)), [
        ("tools/call", {"name": nombre, "arguments": argumentos}),
    ])
    assert rc == 0, err[-2000:]
    return resp[1]["result"]


@requiere_node
def test_ap44_la_tool_que_devuelve_ok_false_llega_como_isError(tmp_path):
    r = _llamar(tmp_path, "vault_read", {"path": "01_Projects/no-existe.md"})
    assert '"ok": false' in r["content"][0]["text"], r
    assert r.get("isError") is True, r


@requiere_node
def test_ap44_la_tool_que_va_bien_no_llega_como_isError(tmp_path):
    r = _llamar(tmp_path, "vault_query_parse", {"query": "por qué PostgreSQL"})
    assert '"ok": false' not in r["content"][0]["text"], r
    assert not r.get("isError"), r
