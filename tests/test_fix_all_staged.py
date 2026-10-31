"""`vault_fix_all --staged` omite lo que el commit no toca, y nada más.

El pre-commit corría los diez pasos en cada commit. Estos tests no regeneran
nada: sustituyen `_ejecutar_paso` por un registro, porque lo que se prueba es
qué pasos se eligen, no lo que cada uno escribe (eso lo cubre `test_fix_all`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_fix_all as vfa  # noqa: E402


@pytest.fixture
def corridos(monkeypatch):
    nombres = []

    def falso(paso, n):
        nombres.append(paso["nombre"])
        return {"paso": n, "nombre": paso["nombre"], "ok": True}

    monkeypatch.setattr(vfa, "_ejecutar_paso", falso)
    return nombres


def _ruta_del_dueno(paso) -> str:
    return f"scripts/{paso.get('script') or paso['modulo'] + '.py'}"


@pytest.mark.parametrize("paso", vfa.PASOS, ids=[p["nombre"] for p in vfa.PASOS])
def test_cambiar_el_generador_corre_su_paso(paso):
    """Un paso cuyos insumos no incluyen su propio script no se repararía al editarlo."""
    assert paso["insumos"] is None or vfa._toca({_ruta_del_dueno(paso)}, paso["insumos"])


@pytest.mark.parametrize("paso", [p for p in vfa.PASOS if p["salidas"]],
                         ids=[p["nombre"] for p in vfa.PASOS if p["salidas"]])
def test_editar_a_mano_un_derivado_corre_el_paso_que_lo_regenera(paso):
    """Lo derivado no se edita a mano (regla 3): si se edita, el hook lo deshace."""
    assert paso["insumos"] is None or vfa._toca(set(paso["salidas"]), paso["insumos"])


def test_un_commit_solo_de_tests_corre_los_pasos_de_siempre(corridos):
    r = vfa.fix_all(cambiados=["tests/test_algo.py"])
    siempre = [p["nombre"] for p in vfa.PASOS if p["insumos"] is None]
    assert corridos == siempre
    assert {o["nombre"] for o in r["omitted"]} == \
        {p["nombre"] for p in vfa.PASOS} - set(siempre)
    assert r["ok"] is True


def test_sin_lista_de_cambios_no_se_omite_nada(corridos):
    r = vfa.fix_all()
    assert corridos == [p["nombre"] for p in vfa.PASOS]
    assert r["omitted"] == []


def test_lo_que_escribe_un_paso_cuenta_como_cambiado_para_los_siguientes(monkeypatch, corridos):
    monkeypatch.setattr(vfa, "PASOS", [
        {"nombre": "a", "insumos": ("a/",), "salidas": ("b/x.json",)},
        {"nombre": "b", "insumos": ("b/",), "salidas": ()},
        {"nombre": "c", "insumos": ("c/",), "salidas": ()},
    ])
    vfa.fix_all(cambiados=["a/fuente.py"])
    assert corridos == ["a", "b"]


def test_el_plan_en_seco_omite_lo_mismo_que_la_corrida(corridos):
    r_seco = vfa.fix_all(dry_run=True, cambiados=["tests/test_algo.py"])
    r = vfa.fix_all(cambiados=["tests/test_algo.py"])
    assert [p["nombre"] for p in r_seco["plan"]] == corridos
    assert r_seco["omitted"] == r["omitted"]


def test_en_este_repo_git_dice_que_hay_en_el_staging():
    assert isinstance(vfa.ficheros_en_staging(), list)


def test_sin_git_el_staging_es_desconocido_y_no_vacio(monkeypatch):
    """`None` corre todo; una lista vacía lo omitiría casi todo en silencio."""
    def roto(*a, **k):
        raise OSError("git no está")

    monkeypatch.setattr(vfa.procesos_git, "ejecutar_git", roto)
    assert vfa.ficheros_en_staging() is None


def test_el_hook_pide_solo_el_staging_y_no_repite_la_corrida():
    # La ruta va entera en un literal: así la encuentra `vault_test_scope` y un
    # cambio en el hook trae este test al carril `dev`.
    hook = (ROOT / ".githooks/pre-commit").read_text(encoding="utf-8")
    llamadas = [linea for linea in hook.splitlines()
                if linea.startswith("python scripts/vault_fix_all.py")]
    assert llamadas == ["python scripts/vault_fix_all.py --staged >/dev/null 2>&1"]
