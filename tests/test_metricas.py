"""Métricas de desarrollo y de producto con objetivo, dueño y tendencia.

Hasta 2026-10-14 el repo medía su deuda —quince baselines con objetivo— pero
no su proceso ni su producto: cuánto tarda la suite, cuántos fallos destapa
cada ronda, qué tal le va al agente del banco. Esas cifras se ejecutaban, se
leían en un log y se perdían. `vault_metricas` las registra con el mismo
contrato de plazo que las baselines (`vault_baseline.validar_plazo`) y guarda
cada observación con el commit que la produjo, para que la tendencia no
dependa de la memoria de nadie.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_gate as gate  # noqa: E402
import vault_metricas as vm  # noqa: E402


def test_toda_metrica_declara_tipo_sentido_origen_y_compromiso():
    ids = [m["id"] for m in vm.METRICAS]
    assert len(ids) == len(set(ids))
    for m in vm.METRICAS:
        assert m["tipo"] in vm.TIPOS, m["id"]
        assert m["sentido"] in vm.SENTIDOS, m["id"]
        assert m["origen"] in vm.ORIGENES, m["id"]
        assert m["que"] and m["fuente"], m["id"]
        assert vm.problemas_de_registro(m) == [], m["id"]


def test_hay_metricas_de_desarrollo_y_de_producto():
    tipos = {m["tipo"] for m in vm.METRICAS}
    assert tipos == set(vm.TIPOS)


def test_cada_calculada_tiene_calculo_y_devuelve_un_numero():
    for m in vm.METRICAS:
        if m["origen"] != "calculada":
            continue
        valor = vm.CALCULOS[m["id"]]()
        assert isinstance(valor, (int, float)), m["id"]


def test_el_check_del_repo_sale_verde():
    r = vm.check()
    assert r["ok"], r["problems"]


def test_un_objetivo_sin_dueno_es_un_problema_de_registro():
    m = {"id": "x", "tipo": "desarrollo", "sentido": "menor", "origen": "observada",
         "que": "q", "fuente": "f", "unidad": "u",
         "objetivo": {"valor": 0, "fecha_limite": "2027-01-01", "cadencia_dias": 30}}
    assert any("dueno" in p for p in vm.problemas_de_registro(m))


def test_sin_objetivo_ni_motivo_es_un_problema():
    m = {"id": "x", "tipo": "desarrollo", "sentido": "menor", "origen": "observada",
         "que": "q", "fuente": "f", "unidad": "u"}
    assert vm.problemas_de_registro(m)


@pytest.mark.parametrize("sentido,valor,meta,esperado", [
    ("menor", 3, 5, "cumple"), ("menor", 6, 5, "en_plazo"),
    ("mayor", 0.95, 0.9, "cumple"), ("mayor", 0.8, 0.9, "en_plazo"),
])
def test_el_estado_respeta_el_sentido(sentido, valor, meta, esperado):
    m = {"sentido": sentido, "objetivo": {"valor": meta, "fecha_limite": "2027-01-01",
                                          "cadencia_dias": 30, "dueno": "d"}}
    assert vm.estado(m, valor, hoy=date(2026, 10, 14))["estado"] == esperado


def test_fuera_de_fecha_y_sin_cumplir_es_vencido():
    m = {"sentido": "menor", "objetivo": {"valor": 0, "fecha_limite": "2026-01-01",
                                          "cadencia_dias": 30, "dueno": "d"}}
    assert vm.estado(m, 2, hoy=date(2026, 10, 14))["estado"] == "vencido"


def test_sin_observaciones_no_sale_como_cumplida():
    m = {"sentido": "menor", "objetivo": {"valor": 0, "fecha_limite": "2027-01-01",
                                          "cadencia_dias": 30, "dueno": "d"}}
    assert vm.estado(m, None)["estado"] == "sin_observar"


def test_el_resumen_de_pytest_se_lee_con_fallos_y_duracion():
    linea = "================= 3 failed, 5507 passed in 4133.59s (1:08:53) ================="
    assert vm.leer_resumen_pytest(linea) == {
        "suite_fallos": 3, "suite_tests": 5510, "suite_duracion_s": 4133.59}
    verde = "====================== 5530 passed in 4338.98s (1:12:18) ======================"
    assert vm.leer_resumen_pytest(verde)["suite_fallos"] == 0


def test_un_log_sin_resumen_no_se_lee_como_cero_fallos():
    with pytest.raises(ValueError):
        vm.leer_resumen_pytest("rc=0\n")


def test_una_observacion_con_commit_inexistente_es_un_problema(monkeypatch):
    monkeypatch.setattr(vm, "_observaciones", lambda: [
        {"metrica": "suite_fallos", "valor": 0, "commit": "0000000", "fecha": "2026-10-14",
         "fuente": "test"}])
    kinds = {p["kind"] for p in vm.check()["problems"]}
    assert "observacion_sin_commit" in kinds


def test_una_observacion_borrada_respecto_de_head_es_un_problema(monkeypatch):
    previa = {"metrica": "suite_fallos", "valor": 0, "commit": "df0ff4d",
              "fecha": "2026-10-14", "fuente": "test"}
    monkeypatch.setattr(vm, "_observaciones_en_head", lambda: [previa])
    monkeypatch.setattr(vm, "_observaciones", lambda: [])
    kinds = {p["kind"] for p in vm.check()["problems"]}
    assert "observacion_borrada" in kinds


def test_una_observacion_de_metrica_desconocida_es_un_problema(monkeypatch):
    monkeypatch.setattr(vm, "_observaciones", lambda: [
        {"metrica": "no_existe", "valor": 1, "commit": "df0ff4d", "fecha": "2026-10-14",
         "fuente": "test"}])
    kinds = {p["kind"] for p in vm.check()["problems"]}
    assert "observacion_de_metrica_desconocida" in kinds


def test_registrar_escribe_y_lo_dice(tmp_path, monkeypatch):
    destino = tmp_path / "obs.json"
    monkeypatch.setattr(vm, "OBSERVACIONES", destino)
    r = vm.registrar([{"metrica": "suite_fallos", "valor": 0}], commit="df0ff4d",
                     fuente="test", hoy=date(2026, 10, 14))
    assert r["ok"] and r["registradas"] == 1
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["observaciones"][0]["commit"] == "df0ff4d"


def test_registrar_rechaza_una_metrica_calculada():
    calculada = next(m["id"] for m in vm.METRICAS if m["origen"] == "calculada")
    r = vm.registrar([{"metrica": calculada, "valor": 1}], commit="df0ff4d", fuente="t")
    assert r["ok"] is False


def test_el_documento_es_derivado():
    assert vm.check_doc()["ok"], "python scripts/vault_metricas.py --doc"


def test_la_puerta_esta_en_el_registro():
    assert any(p["id"] == "metricas" for p in gate.PUERTAS)
