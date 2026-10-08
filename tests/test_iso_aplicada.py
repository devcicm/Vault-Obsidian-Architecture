"""Una ISO del registro la aplica una tool que existe, y declara cuánto.

`ISO_COVERAGE` es alineación, no certificación. Lo que la hace algo más que
una lista de citas es que cada entrada nombra tools vivas y su `cobertura`:
`clausula` si ejercen la cláusula citada, `parcial` con el `hueco` escrito.
`vault_norms --check-framework` falla si una tool deja de existir o si una
cobertura parcial calla lo que falta.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_fundamentals_catalog import ISO_COBERTURAS, ISO_COVERAGE  # noqa: E402
from vault_norms_engine import framework_drift_check, iso_coverage_check  # noqa: E402


def test_toda_iso_declara_cobertura_y_el_hueco_de_la_parcial():
    for e in ISO_COVERAGE:
        assert e["cobertura"] in ISO_COBERTURAS, e["id"]
        if e["cobertura"] == "parcial":
            assert e["hueco"].strip(), e["id"]


def test_el_registro_real_pasa_el_guard():
    r = iso_coverage_check()
    assert r["ok"], r


def test_una_tool_que_desaparece_hace_fallar_el_guard(tmp_path):
    """Un directorio de scripts sin las tools: todas las citas quedan sin ejecutor."""
    (tmp_path / "vault_norms.py").write_text("", encoding="utf-8")
    r = iso_coverage_check(tmp_path)
    assert not r["ok"]
    ids = {x["id"] for x in r["tools_inexistentes"]}
    assert "ISO-23894" in ids and "ISO-25051" in ids
    assert {"id": "ISO-42010", "tool": "vault_norms"} not in r["tools_inexistentes"]


def test_parcial_sin_hueco_y_cobertura_desconocida_fallan(monkeypatch):
    import vault_fundamentals_catalog as cat
    falsas = [
        {"id": "ISO-X1", "tools": ["vault_norms"], "cobertura": "parcial"},
        {"id": "ISO-X2", "tools": ["vault_norms"], "cobertura": "total"},
        {"id": "ISO-X3", "tools": [], "cobertura": "clausula"},
    ]
    monkeypatch.setattr(cat, "ISO_COVERAGE", falsas)
    r = iso_coverage_check()
    assert r["cobertura_invalida"] == ["ISO-X1", "ISO-X2", "ISO-X3"]
    assert framework_drift_check()["ok"] is False


def test_el_manifiesto_publica_la_cobertura_del_registro():
    """La tabla del manifiesto se escribe a mano: que diga lo mismo que el registro."""
    texto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    assert "Alineación, no certificación" in texto
    for e in ISO_COVERAGE:
        fila = re.search(rf"^\| \*\*{re.escape(e['id'])}\*\* \|.*$", texto, re.M)
        assert fila, e["id"]
        celdas = [c.strip() for c in fila.group(0).strip("|").split("|")]
        assert celdas[1] == e["norm"], e["id"]
        assert celdas[-1] == e["cobertura"], e["id"]
        for t in e["tools"]:
            assert f"`{t}`" in celdas[4], (e["id"], t)
