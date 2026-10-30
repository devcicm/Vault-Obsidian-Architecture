"""A-04 — `slugify_strict(x)[:60]` cortaba en medio y dejaba un guion colgando.

El slug cortado acababa en `-` (`...-.md`), que `slugify_strict` ya declara
inadmisible como clave de ruta: la auditoria CN-04 lo marcaba en la nota recien
escrita por la propia tool.
"""
import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
CORTADORES = ["vault_bibliography_save", "vault_bug_save", "vault_incident_save",
              "vault_ncr_save", "vault_privacy_save", "vault_risk_save"]


@pytest.mark.parametrize("script", CORTADORES)
def test_el_corte_a_60_no_deja_guion_colgante(script):
    fuente = (SCRIPTS / f"{script}.py").read_text(encoding="utf-8")
    cortes = re.findall(r"slugify_strict\([^)]*\)\[:60\](\.strip\(\"-\"\))?", fuente)
    assert cortes, script
    assert all(cortes), f"{script}: el slice [:60] debe cerrar con .strip(\"-\")"


def test_el_caso_medido_termina_sin_guion():
    sys.path.insert(0, str(SCRIPTS))
    from vault_lib import slugify_strict
    titulo = "a" * 59 + " bbb"
    assert slugify_strict(titulo)[:60].endswith("-")
    assert not slugify_strict(titulo)[:60].strip("-").endswith("-")
