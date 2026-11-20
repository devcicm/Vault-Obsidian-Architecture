"""The onboarded vault is integrated: no concept or module note is an orphan (2026-11-20).

Measured re-onboarding this repository after 4e8d9495 (README headings are now
detected) and 9085ba17 (content from HEAD's history): the fresh vault scored 74
instead of 100 because 13 notes were orphans, 5 README concepts and 8 module
notes. Only the section indexes listed them, and an index does not integrate a
note. The skill promises that the resulting vault needs no healing: the project
overview now links every concept and module note the onboarding wrote, in a
`## Mapa del proyecto` section the merge appends once.
"""

from apoyo import correr_tool, entorno
from test_onboard_escalonado import PROYECTO, _onboard, proyecto, vault  # noqa: F401


def test_ninguna_nota_de_concepto_ni_de_modulo_queda_huerfana(vault):
    v, _ = vault
    r = correr_tool("vault_audit", env=entorno(v, VAULT_TOOL_TIMEOUT="600"), timeout=600)
    huerfanas = [o["path"] for o in (r.envelope.get("issues") or {}).get("orphans", [])
                 if o["path"].startswith(("07_Knowledge/", "11_Code/"))]
    assert huerfanas == [], huerfanas


def test_el_overview_publica_el_mapa_y_una_segunda_corrida_no_lo_repite(vault, proyecto):
    v, _ = vault
    overview = (v / "01_Projects" / PROYECTO / "overview.md").read_text(encoding="utf-8")
    assert overview.count("## Mapa del proyecto") == 1
    assert "[[11_Code/" in overview
    _onboard(v, proyecto)
    otra = (v / "01_Projects" / PROYECTO / "overview.md").read_text(encoding="utf-8")
    assert otra.count("## Mapa del proyecto") == 1 and otra == overview
