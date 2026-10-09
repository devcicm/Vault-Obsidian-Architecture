"""`vault_drift_detect --mode report` no cae ante una fecha sin zona.

Regla 7: sobre una copia de /ans, el report del banco devolvía
UNEXPECTED_ERROR («can't compare offset-naive and offset-aware datetimes»).
Un vault ajeno escribe `updatedAt: 2026-01-01` —sin hora ni zona— y
`_find_coverage` lo comparaba con el `since` del snapshot, que sí la lleva.
`_en_utc` ya protegía la vigencia; la cobertura no pasaba por él. El arreglo
va en el dueño de la lectura, `_parse_iso`: toda fecha que devuelve tiene zona.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_drift_detect as dd  # noqa: E402


def test_parse_iso_siempre_devuelve_fecha_con_zona():
    for crudo in ("2026-01-01", "2026-01-01T10:00:00", "2026-01-01T10:00:00Z",
                  "2026-01-01T10:00:00+02:00"):
        assert dd._parse_iso(crudo).tzinfo is not None, crudo


def test_la_cobertura_compara_una_nota_sin_zona_con_el_snapshot(monkeypatch):
    monkeypatch.setattr(dd, "_load_code_index", lambda: [])
    monkeypatch.setattr(dd, "_load_search_index", lambda: [
        {"title": "modulo", "path": "01_Projects/modulo.md", "updatedAt": "2026-10-10"},
        {"title": "viejo", "path": "01_Projects/viejo.md", "updatedAt": "2020-01-01"},
    ])
    documentadas, sin_documentar = dd._find_coverage(
        ["src/modulo.py", "src/viejo.py"], "p", "2026-10-09T00:00:00Z")
    assert [d["file"] for d in documentadas] + [u["file"] for u in sin_documentar]
