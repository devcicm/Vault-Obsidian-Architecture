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
import vault_grafo_import as gi  # noqa: E402

CORTADORES = ["vault_bibliography_save", "vault_bug_save", "vault_incident_save",
              "vault_ncr_save", "vault_privacy_save", "vault_risk_save"]


#: Any slice of a strict slug, whatever its length. Derived from the source so
#: that a new sibling writer cannot escape the check by being left off a list.
_CORTE = re.compile(r"slugify_strict\([^)]*\)\[:\d+\](\.strip\(\"-\"\))?")


def _cortadores_en_el_codigo():
    return sorted(p.stem for p in SCRIPTS.glob("*.py")
                  if _CORTE.search(gi.codigo_de(p).read_text(encoding="utf-8")))


def test_la_lista_medida_cubre_a_todos_los_escritores_que_cortan():
    encontrados = _cortadores_en_el_codigo()
    assert set(CORTADORES) <= set(encontrados), encontrados


@pytest.mark.parametrize("script", _cortadores_en_el_codigo())
def test_el_corte_a_60_no_deja_guion_colgante(script):
    fuente = gi.codigo_de(SCRIPTS / f"{script}.py").read_text(encoding="utf-8")
    cortes = _CORTE.findall(fuente)
    assert cortes, script
    assert all(cortes), f"{script}: un slice del slug debe cerrar con .strip(\"-\")"


def test_el_caso_medido_termina_sin_guion():
    sys.path.insert(0, str(SCRIPTS))
    from vault_lib import slugify_strict
    titulo = "a" * 59 + " bbb"
    assert slugify_strict(titulo)[:60].endswith("-")
    assert not slugify_strict(titulo)[:60].strip("-").endswith("-")
