"""Review dates are written and read on the same clock: UTC.

Measured 2026-11-18 at 18:09 in UTC-6: `vault_risk_save` stamps `revisado_en`
with `vault_lib.utcnow` (already the 19th in UTC), while every reader of review
dates — `vault_audit`'s AI-risk work list, `vault_drift_detect --mode
antiguedad/conservacion` and `gestion_de_normas` — defaulted to the local
`date.today()` (still the 18th). A risk reviewed a minute earlier was then
"posterior a hoy" and listed as unreadable for the rest of the local day.
The standard's timestamps are UTC (ISO 8601 with `Z`): the readers ask one
owner for "today", in UTC.
"""
import re
from datetime import datetime, timezone

from apoyo import ROOT

import vault_norms_catalog


def test_hoy_es_la_fecha_utc():
    assert vault_norms_catalog.hoy_utc() == datetime.now(timezone.utc).date()


def test_ningun_lector_de_revisiones_usa_la_fecha_local():
    lectores = ("scripts/vault_audit.py", "scripts/vault_drift_detect.py",
                "vault/kernel/normativa/norms_catalog.py")
    locales = [f"{f}:{n}" for f in lectores
               for n, linea in enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1)
               if re.search(r"\b_?date\.today\(\)", linea)]
    assert locales == []


def test_una_revision_de_hoy_no_es_posterior_a_hoy():
    hoy = vault_norms_catalog.hoy_utc()
    estado = vault_norms_catalog.estado_de_revision(hoy.isoformat(), 90, hoy)
    assert "problema" not in estado, estado
    assert estado["vencida"] is False
