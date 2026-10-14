"""`vault run` de una tool que solo sirve el MCP decía que no estaba instalada.

`vault_backup_base64` y `vault_restore_base64` son JavaScript nativo del
servidor MCP (`vault_mcp_catalog.NATIVE_JS_TOOLS`): viajan en la wheel y
funcionan por MCP. La CLI respondía «aún no está instalada… esta instalación no
la trae», así que un agente consumidor concluía que le faltaba algo y no tenía
backup. El catálogo empaquetado ya llevaba `js_native_tools`; nadie lo leía.

Lo encontró una sesión de agente consumidor sobre la wheel el 2026-10-14.
"""

from __future__ import annotations

import json

from vault import product_cli
from vault.meta_toolkit import resolucion_producto
from vault.meta_toolkit.catalogo_producto import catalogo_producto


def _solo_mcp():
    return sorted(n for n, t in catalogo_producto().items() if t.via == "mcp")


def test_el_catalogo_marca_las_tools_que_sirve_el_mcp():
    assert _solo_mcp() == ["vault_backup_base64", "vault_restore_base64"]
    assert all(t.via == "cli" for n, t in catalogo_producto().items()
               if t.execution_module is not None)


def test_run_de_una_tool_solo_mcp_lo_dice_y_no_que_falta(monkeypatch, capsys):
    monkeypatch.setattr(product_cli.metadata, "version", lambda _: "40.34")
    nombre = _solo_mcp()[0]
    assert product_cli.main(["run", nombre]) == product_cli.EXIT_NOT_INSTALLED
    err = json.loads(capsys.readouterr().err)
    assert err["state"] == resolucion_producto.KNOWN_NOT_INSTALLED
    assert "MCP" in err["message"] and "no está instalada" not in err["message"], err
    assert "mcp-path" in err["recovery"]["hint"], err


def test_tools_show_publica_por_donde_se_sirve(monkeypatch, capsys):
    monkeypatch.setattr(product_cli.metadata, "version", lambda _: "40.34")
    assert product_cli.main(["tools", "show", "vault_backup_base64"]) == 0
    assert json.loads(capsys.readouterr().out)["via"] == "mcp"
