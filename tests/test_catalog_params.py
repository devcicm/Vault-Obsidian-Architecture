"""AP-40 — el contrato publicado es el que la CLI acepta.

El defecto que estos tests cierran no era una tool mal documentada: era la mitad
del catálogo MCP publicando flags que su argparse rechaza. Pasó inadvertido
durante versiones porque el guard de sincronía comparaba el JSON contra el
Python — y las dos copias contenían la misma equivocación.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_mcp_catalog as cat  # noqa: E402
import vault_norms  # noqa: E402


# ── Extracción desde argparse ────────────────────────────────────────────────

def test_argparse_params_lee_los_flags_reales_de_un_script():
    params = cat.argparse_params("vault_impact.py")
    assert "changed" in params, "el flag que la CLI sí acepta"
    assert "path" not in params, "el param fantasma que el catálogo publicaba"


def test_los_tipos_salen_de_la_accion_de_argparse():
    params = cat.argparse_params("vault_tags.py")
    assert params["audit"]["type"] == "boolean"      # store_true
    assert params["rename"]["type"] == "array"       # nargs
    assert params["suggest"]["type"] == "string"


def test_un_script_inexistente_no_revienta():
    assert cat.argparse_params("no-existe-jamas.py") == {}
    assert cat.argparse_params("") == {}


def test_los_posicionales_no_se_publican():
    """El servidor MCP compone `--<param>`: un posicional publicado así falla."""
    params = cat.argparse_params("vault_query_parse.py")
    assert "query" not in params


# ── Reconciliación ───────────────────────────────────────────────────────────

def test_reconciled_params_conserva_la_descripcion_escrita_a_mano():
    py = cat.TOOLS_CATALOG["vault_tags"]
    escrita = py["params"]["audit"]["description"]
    assert cat.reconciled_params(py)["audit"]["description"] == escrita


def test_reconciled_params_descarta_lo_que_la_cli_rechaza():
    for nombre, py in cat.TOOLS_CATALOG.items():
        reales = cat.argparse_params(py.get("script", ""))
        if not reales:
            continue
        sobran = [p for p in cat.reconciled_params(py) if p not in reales]
        assert not sobran, f"{nombre} publicaría {sobran}"


def test_sin_argparse_legible_se_publica_lo_declarado():
    """Una tool archivada o sin script no pierde su contrato documentado."""
    falsa = {"script": "", "params": {"x": {"type": "string", "description": "d"}}}
    assert cat.reconciled_params(falsa) == falsa["params"]


# ── El guard ─────────────────────────────────────────────────────────────────

def test_check_params_esta_en_verde_sobre_el_json_real():
    r = cat.check_params()
    assert r["ok"], r["problems"]
    assert r["tools_checked"] > 50, "el guard tiene que estar mirando casi todo"


def test_check_params_falla_cuando_alguien_publica_un_flag_inventado(tmp_path):
    """La prueba activa del guard: si no falla aquí, no protege nada."""
    real = json.loads(
        (ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8")
    )
    tools = real.get("tools", real)
    tools["vault_tags"]["inputSchema"]["properties"]["flag-inventado"] = {"type": "string"}
    roto = tmp_path / "tools-catalog.json"
    roto.write_text(json.dumps(real), encoding="utf-8")

    r = cat.check_params(str(roto))
    assert not r["ok"]
    assert any(p["tool"] == "vault_tags" for p in r["problems"])


def test_check_params_reporta_el_json_ausente(tmp_path):
    r = cat.check_params(str(tmp_path / "no-esta.json"))
    assert not r["ok"]


# ── La norma existe y tiene enforcement real ─────────────────────────────────

def test_ap40_esta_en_el_catalogo_con_enforcement_real():
    norma = next((n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-40"), None)
    assert norma is not None
    assert norma["enforcement"] in ("guard", "audit", "guard+audit", "recommended")
    assert "vault_mcp_catalog --check-params" in norma["tools_detecting"]


def test_el_audit_de_normas_conoce_ap40():
    fuente = (SCRIPTS / "vault_norms.py").read_text(encoding="utf-8")
    assert '"AP-40"' in fuente
    assert "check_params" in fuente


def test_el_schema_json_se_deriva_no_se_copia():
    """Si alguien vuelve a construir el schema desde `params` sin conciliar,
    la divergencia regresa entera y en silencio."""
    fuente = (SCRIPTS / "vault_mcp_catalog.py").read_text(encoding="utf-8")
    assert "reconciled_params(py_tool)" in fuente
