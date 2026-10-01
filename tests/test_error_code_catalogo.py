"""D3 — todo código de error emitido está en `ERROR_CATALOG` (AP-52).

`emit_error` no fallaba con un código inventado: `get_error` caía a
UNEXPECTED_ERROR y el envelope salía con el nombre nuevo y la recuperación de
otro —`critical`/`manual` para un argumento mal escrito—. Había 104 así: 41 por
`emit_error`, 58 en envelopes construidos a mano y 5 en el servidor MCP. El
detector de AP-52 solo veía el envelope **sin** `error_code`.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_error_contract  # noqa: E402
from vault.kernel.errores import ERROR_CATALOG, ErrorCode, construir_error  # noqa: E402


def test_el_enum_se_deriva_del_catalogo():
    assert [c.value for c in ErrorCode] == list(ERROR_CATALOG)
    assert ErrorCode.INVALID_PATH == "INVALID_PATH"


def test_un_miembro_del_enum_viaja_como_cadena():
    e = construir_error("t", ErrorCode.INVALID_PATH)
    assert type(e["error_code"]) is str
    assert json.loads(json.dumps(e))["error_code"] == "INVALID_PATH"
    assert e["recovery"] == ERROR_CATALOG["INVALID_PATH"]["recovery"]


def test_ap52_un_codigo_de_un_veredicto_tiene_su_recuperacion():
    """Antes salía como UNEXPECTED_ERROR critical: el consumidor abortaba."""
    e = construir_error("vault_changelog_check", "PARSE_FAILED")
    assert e["severity"] != "critical"
    assert e["recovery"]["action"] == "fix_input"


def test_ap52_detecta_codigos_inventados_en_las_tres_formas(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_x.py").write_text(
        "emit_error('vault_x', 'INVENTADO_A')\n"
        "emit_error('vault_x', code='INVENTADO_B')\n"
        "r = {'ok': False, 'error_code': 'INVENTADO_C'}\n"
        "emit_error('vault_x', 'INVALID_PATH')\n",
        encoding="utf-8",
    )
    (tmp_path / "mcp" / "nodejs").mkdir(parents=True)
    (tmp_path / "mcp" / "nodejs" / "srv.mjs").write_text(
        'return formatToolError("INVENTADO_D", "x");\n'
        'return { code: "INVENTADO_E", message: "y" };\n'
        'return formatToolError("INVALID_ARGS", "z");\n',
        encoding="utf-8",
    )
    fuera = vault_error_contract.codigos_fuera_del_catalogo(tmp_path)
    assert sorted(f["code"] for f in fuera) == [
        "INVENTADO_A", "INVENTADO_B", "INVENTADO_C", "INVENTADO_D", "INVENTADO_E",
    ]


def test_ap52_hoy_no_hay_codigos_fuera_del_catalogo():
    assert vault_error_contract.codigos_fuera_del_catalogo() == []


def test_ap52_la_puerta_los_bloquea(monkeypatch):
    monkeypatch.setattr(
        vault_error_contract, "codigos_fuera_del_catalogo",
        lambda raiz=None: [{"module": "scripts/x.py", "line": 1, "code": "NUEVO"}],
    )
    r = vault_error_contract.scan()
    assert r["ok"] is False
    assert r["codes_outside_catalog"][0]["code"] == "NUEVO"
