"""AP-42 — por MCP, una tool con modo `--json` contesta en JSON.

Medido en v40.34: cinco tools (`vault_move`, `vault_folder_registry`,
`vault_diagram_export`, `vault_graph_inspect`, `vault_graph_fix`) hablan a una
persona por defecto y a una máquina con `--json`. `vault_smoke` se lo pedía y
daba el contrato por cumplido; el servidor MCP no, así que el agente recibía
`{"structured": false, "warning": "non_json_output", "raw_output": "Movido: …"}`
sin `ok` propio, sin `backlinks_count`, sin nada que leer.

El criterio tiene un dueño, `vault_mcp_catalog.acepta_modo_json`; el catálogo
lo publica como `json_flag` y el servidor lo cumple.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

from test_mcp_runner import SesionMCP, _init_vault

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_mcp_catalog import TOOLS_CATALOG, acepta_modo_json  # noqa: E402

CATALOGO = REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json"


def test_el_catalogo_publica_json_flag_con_el_criterio_del_dueno():
    publicado = json.loads(CATALOGO.read_text(encoding="utf-8"))["tools"]
    con_flag = {t for t, e in publicado.items() if e.get("json_flag") is True}
    esperado = {t for t, e in TOOLS_CATALOG.items() if acepta_modo_json(e.get("script", ""))}
    assert con_flag == esperado
    assert "vault_move" in con_flag and "vault_search" not in con_flag


def test_un_json_que_toma_valor_no_es_modo_json():
    # `vault_mcp_catalog --json <ruta>` lee un fichero: pedirle `--json` a
    # secas lo rompería.
    assert acepta_modo_json("vault_mcp_catalog.py") is False


@pytest.mark.skipif(shutil.which("node") is None, reason="el servidor MCP necesita Node")
def test_vault_move_por_mcp_devuelve_su_envelope(tmp_path):
    vault = _init_vault(tmp_path / "vault")
    (vault / "07_Knowledge").mkdir(exist_ok=True)
    (vault / "07_Knowledge" / "origen.md").write_text("# origen\n", encoding="utf-8")
    (vault / "07_Knowledge" / "cita.md").write_text("Ver [[origen]].\n", encoding="utf-8")
    sesion = SesionMCP(vault)
    try:
        r = sesion.llamar("vault_move", {"from": "07_Knowledge/origen.md",
                                         "to": "03_Decisions/origen.md", "impact": True})
    finally:
        sesion.cerrar()
    env = json.loads(r["result"]["content"][0]["text"])
    assert env.get("warning") != "non_json_output", env
    assert env["ok"] is True and env["backlinks_count"] == 1, env
