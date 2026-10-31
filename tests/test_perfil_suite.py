"""`slow` se deriva del perfil medido, no se escribe a mano (v41.26).

El dueño es `vault.meta_toolkit.perfil_suite`; lo leen el conftest (marca),
`reparto` (shards) y `vault_test_scope` (carril `dev`).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import reparto
from vault.meta_toolkit import perfil_suite

TESTS = Path(__file__).resolve().parent


def _perfil(ruta: Path, segundos: dict) -> Path:
    ruta.write_text(json.dumps({"_fuente": "test", "segundos_por_modulo": segundos}),
                    encoding="utf-8")
    return ruta


def test_lento_es_llegar_al_umbral_por_modulo():
    u = perfil_suite.UMBRAL_LENTO_S
    assert perfil_suite.lentos({"a": u, "b": u - 0.1}) == {"a": u}


def test_sin_perfil_ningun_modulo_es_lento(tmp_path):
    assert perfil_suite.pesos(tmp_path / "no-esta.json") == {}
    assert perfil_suite.lentos({}) == {}


def test_el_reparto_pesa_con_el_mismo_perfil():
    assert reparto._pesos() == perfil_suite.pesos()


def test_ningun_modulo_de_test_se_marca_slow_a_mano():
    """Una marca escrita a mano es una segunda copia del perfil (AP-05)."""
    a_mano = []
    for f in sorted(TESTS.glob("test_*.py")):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Attribute) and n.attr == "slow"
                    and isinstance(n.value, ast.Attribute) and n.value.attr == "mark"):
                a_mano.append(f"{f.name}:{n.lineno}")
    assert a_mano == []


def test_el_conftest_marca_slow_justo_a_los_modulos_lentos(request):
    lentos = perfil_suite.lentos()
    for item in request.session.items:
        marcado = item.get_closest_marker("slow") is not None
        assert marcado == (reparto.modulo_de(item.nodeid) in lentos), item.nodeid


def test_refrescar_sustituye_lo_medido_y_conserva_lo_demas(tmp_path):
    perfil = _perfil(tmp_path / "perfil.json", {"test_a": 30.0, "test_b": 5.0, "test_c": 1.0})
    spans = tmp_path / "spans.json"
    spans.write_text(json.dumps({"spans": [
        {"modulo": "test_a", "worker": "gw0", "trabajo_s": 2.0},
        {"modulo": "test_b", "worker": "gw0", "trabajo_s": 20.0},
        {"modulo": "test_b", "worker": "gw1", "trabajo_s": 10.0},
    ]}), encoding="utf-8")
    r = perfil_suite.refrescar(spans, perfil, hoy="2026-10-31")
    assert r["ok"] and r["medidos"] == 2
    assert perfil_suite.pesos(perfil) == {"test_a": 2.0, "test_b": 30.0, "test_c": 1.0}
    assert (r["entran_en_slow"], r["salen_de_slow"]) == (["test_b"], ["test_a"])
    assert b"\r\n" not in perfil.read_bytes()
    assert list(tmp_path.glob("*.tmp")) == []


def test_refrescar_sin_spans_no_toca_el_perfil(tmp_path):
    perfil = _perfil(tmp_path / "perfil.json", {"test_a": 30.0})
    antes = perfil.read_bytes()
    r = perfil_suite.refrescar(tmp_path / "no-hay.json", perfil)
    assert r["ok"] is False and r["error_code"] == "DATA_FILE_CORRUPT"
    assert perfil.read_bytes() == antes
