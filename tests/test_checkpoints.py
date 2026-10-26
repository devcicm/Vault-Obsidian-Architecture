"""Checkpoints: una sesion interrumpida no repite todo ni declara PASS de mas."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audits" / "architecture"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _modulo():
    import importlib.util

    spec = importlib.util.spec_from_file_location("checkpoints",
                                                  BASE / "checkpoints.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_una_corrida_registra_su_run_id_y_su_sha(tmp_path):
    mod = _modulo()
    datos = mod.iniciar(tmp_path, "puertas", "a" * 40)
    assert datos["run_id"].startswith("RUN-")
    assert datos["sha"] == "a" * 40
    assert datos["eventos"][0]["evento"] == "RUN_CREATED"
    assert (tmp_path / "manifiesto-corrida.json").is_file()


def test_una_unidad_interrumpida_no_es_pass(tmp_path):
    """La parte que mas importa: lo que se quedo a medias NO cuenta como verde."""
    mod = _modulo()
    mod.iniciar(tmp_path, "puertas", "b" * 40)
    estado = mod.estado(tmp_path)
    assert estado["pendientes"] == ["puertas"]
    assert estado["advertencia"]
    assert "puertas" not in estado["completadas"]


def test_una_unidad_pasada_no_se_repite(tmp_path):
    mod = _modulo()
    mod.iniciar(tmp_path, "puertas", "c" * 40)
    mod.registrar(tmp_path, "UNIT_PASSED", "26/26", "puertas")
    mod.registrar(tmp_path, "UNIT_STARTED", "", "suite")
    mod.registrar(tmp_path, "UNIT_PASSED", "6280 passed", "suite")
    mod.registrar(tmp_path, "RUN_COMPLETED", "", "")
    estado = mod.estado(tmp_path)
    assert estado["pendientes"] == []
    assert estado["completadas"] == ["puertas", "suite"]
    assert estado["fallidas"] == []


def test_una_unidad_fallida_no_pendiente_ni_pasada(tmp_path):
    mod = _modulo()
    mod.iniciar(tmp_path, "puertas", "d" * 40)
    mod.registrar(tmp_path, "UNIT_FAILED", "1 gate roja", "puertas")
    estado = mod.estado(tmp_path)
    assert estado["fallidas"] == ["puertas"]
    assert "puertas" not in estado["completadas"]


def test_reanudar_una_corrida_marca_el_resumen(tmp_path):
    mod = _modulo()
    mod.iniciar(tmp_path, "puertas", "e" * 40)
    mod.iniciar(tmp_path, "suite", "e" * 40)
    eventos = mod._cargar(tmp_path)["eventos"]
    assert any(e["evento"] == "RUN_RESUMED" for e in eventos)


def test_los_eventos_desconocidos_se_rechazan(tmp_path):
    mod = _modulo()
    mod.iniciar(tmp_path, "puertas", "f" * 40)
    try:
        mod.registrar(tmp_path, "EVENTO_INVENTADO", "", "puertas")
    except ValueError:
        return
    raise AssertionError("un evento desconocido debe rechazarse")


def test_los_artefactos_se_registran_con_su_hash(tmp_path):
    mod = _modulo()
    mod.iniciar(tmp_path, "suite", "0" * 40)
    arte = tmp_path / "junit.xml"
    arte.write_text("<testsuites/>", encoding="utf-8")
    mod.registrar(tmp_path, "UNIT_PASSED", "ok", "suite", str(arte))
    eventos = mod._cargar(tmp_path)["eventos"]
    creados = [e for e in eventos if e["evento"] == "ARTIFACT_CREATED"]
    assert creados and "sha256=" in creados[0]["detalle"]
