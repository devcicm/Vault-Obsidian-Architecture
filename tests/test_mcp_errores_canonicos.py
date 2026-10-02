"""AP-52 — los errores del servidor MCP tienen la forma del catálogo.

Medido en v40.34: los fallos que construye el propio servidor (argumentos
rechazados, guard chain, tool inexistente, excepción del transporte) salían como
`{ok, error_code, tool, message}`. Sin `category`, `severity`, `recovery` ni
`timestamp`: el agente no tenía `recovery.action` por el que decidir justo en
los errores que no pasan por `wrap_main`, porque el `.mjs` está al otro lado de
la frontera de lenguaje y ningún guard de Python lo mira.

El catálogo cruza por la pasarela (`tools-catalog.json`, clave `errors`) y el
criterio de forma es el de Python, `problemas_de_forma`, aplicado al envelope
real que llega por stdio.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from test_mcp_runner import SesionMCP, _init_vault

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

from vault.kernel.errores import ERROR_CATALOG, problemas_de_forma  # noqa: E402
from vault_mcp_catalog import errores_para_transporte  # noqa: E402

SERVIDOR = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
CATALOGO = REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json"


def test_ap52_la_pasarela_lleva_el_catalogo_de_errores_entero():
    publicado = json.loads(CATALOGO.read_text(encoding="utf-8"))
    assert publicado.get("errors") == errores_para_transporte()
    assert set(publicado["errors"]) == set(ERROR_CATALOG)


def test_ap52_todo_codigo_literal_del_servidor_esta_en_el_catalogo():
    """Un código fuera del catálogo cae a UNEXPECTED_ERROR: el agente recibiría
    la recuperación de otro fallo."""
    fuente = SERVIDOR.read_text(encoding="utf-8")
    usados = set(re.findall(r'formatToolError\(\s*"([^"]+)"', fuente))
    usados |= set(re.findall(r'construirError\([^,]+,\s*"([^"]+)"', fuente))
    usados |= set(re.findall(r'\bcode:\s*"([A-Za-z_0-9]+)"', fuente))
    assert usados, "el detector no encontró ningún código: revisar la regex"
    assert usados - set(ERROR_CATALOG) == set()


@pytest.mark.skipif(shutil.which("node") is None, reason="el servidor MCP necesita Node")
@pytest.mark.parametrize("tool,argumentos,codigo", [
    ("vault_read", {"no_existe": 1}, "INVALID_ARGS"),
    ("vault_que_no_existe", {}, "tool_not_found"),
    ("vault_write", {"folder": "07_Knowledge", "title": "Corta", "content": "una linea"},
     "GUARD_CHAIN_FAILED"),
])
def test_ap52_el_rechazo_del_transporte_sale_canonico(tmp_path, tool, argumentos, codigo):
    vault = _init_vault(tmp_path / "vault")
    sesion = SesionMCP(vault)
    try:
        r = sesion.llamar(tool, argumentos)
    finally:
        sesion.cerrar()
    env = json.loads(r["result"]["content"][0]["text"])
    assert env["error_code"] == codigo, env
    # Decía `"tool": "unknown"` al bloquear la cadena de guardas: el servidor
    # sabía qué tool había rechazado y no lo pasaba al envelope.
    assert env["tool"] == tool, env
    assert problemas_de_forma(env) == [], env
    assert env["recovery"]["action"] == ERROR_CATALOG[codigo]["recovery"]["action"]
