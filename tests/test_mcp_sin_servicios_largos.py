"""AP-44 — el MCP ofrecía una tool que, llamada por MCP, no puede terminar.

`vault_token_service` arranca un servidor HTTP (`serve_forever`) y no vuelve
hasta que lo matan. Por MCP cada llamada acababa en `TOOL_TIMEOUT` y el
servidor la seguía anunciando en `tools/list`: una promesa que el consumidor no
puede cobrar. Se lanza como proceso propio, desde la CLI (`vault run
vault_token_service`). La tool no se borra (no-derogación): deja de exponerse
por MCP, con el motivo en el registro `SERVICIOS_DE_PROCESO_LARGO`.

Lo encontró el barrido de tools instaladas el 2026-10-14.
"""

import json
import sys
from pathlib import Path

from test_mcp_instalado import _entorno, _instalacion, _sesion, _vault, requiere_node

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_mcp_catalog as cat  # noqa: E402


def test_ap44_los_servicios_de_proceso_largo_no_se_exponen_por_mcp():
    assert "vault_token_service" in cat.SERVICIOS_DE_PROCESO_LARGO
    tools = json.loads((RAIZ / "mcp" / "nodejs" / "tools-catalog.json")
                       .read_text(encoding="utf-8"))["tools"]
    for nombre in cat.SERVICIOS_DE_PROCESO_LARGO:
        assert nombre in cat.TOOLS_CATALOG, nombre  # sigue catalogada
        assert tools[nombre]["exposed_via_mcp"] is False, nombre


@requiere_node
def test_ap44_el_servidor_instalado_no_la_anuncia_ni_la_lanza(tmp_path):
    site = tmp_path / "site"
    servidor = _instalacion(site)
    vault = _vault(tmp_path / "vault")
    rc, resp, err = _sesion(servidor, vault, _entorno(site, VAULT_ROOT=str(vault)), [
        ("tools/list", {}),
        ("tools/call", {"name": "vault_token_service", "arguments": {}}),
    ])
    assert rc == 0, err[-2000:]
    assert "vault_token_service" not in {t["name"] for t in resp[1]["result"]["tools"]}
    assert resp[2]["result"].get("isError") is True
