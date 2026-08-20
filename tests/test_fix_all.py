"""Tests de `vault_fix_all` — el orquestador de artefactos derivados.

Tres familias:

  1. **El plan es estable**: hay 7 pasos, en orden, y cada uno es una tool que
     existe y acepta el flag que se le pide (AP-40 aplicado a la orquestación).
  2. **Dry-run no escribe**: `--dry-run` devuelve el plan sin ejecutar nada.
  3. **La ejecución real regenera**: correr `--step N` individual no rompe, y el
     conjunto devuelve `ok` con todos los pasos reportados.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_fix_all as vfa  # noqa: E402


def test_siete_pasos_en_el_orden_canonico():
    assert [p["nombre"] for p in vfa.PASOS] == [
        "tools_catalog",
        "env_table",
        "field_compat",
        "arquitectura",
        "blueprint",
        "doc_counts",
        "doc_sync",
    ]


def test_cada_paso_apunta_a_un_script_que_existe():
    for paso in vfa.PASOS:
        script = ROOT / "scripts" / paso["script"]
        assert script.exists(), f"{paso['script']} no existe en scripts/"


@pytest.mark.parametrize("paso", range(1, 8))
def test_cada_paso_individual_ejecuta_sin_romper(paso):
    """Cada paso por separado debe poder ejecutarse (--step N)."""
    r = vfa.fix_all(solo_paso=paso)
    assert r["ok"], f"paso {paso} falló: {r['results'][0]}"
    assert r["steps_total"] == 1


def test_dry_run_no_ejecuta():
    r = vfa.fix_all(dry_run=True)
    assert r["dry_run"] is True
    assert r["ok"] is True
    assert len(r["plan"]) == len(vfa.PASOS)
    assert all("nombre" in p and "script" in p for p in r["plan"])


def test_el_conjunto_reporta_todos_los_pasos():
    """El envelope del conjunto lista cada paso con su resultado."""
    r = vfa.fix_all()
    assert r["steps_total"] == 7
    assert r["steps_ok"] == 7, [x["nombre"] for x in r["results"] if not x["ok"]]
    assert r["steps_failed"] == 0
    assert r["failed"] == []
    assert len(r["results"]) == 7
