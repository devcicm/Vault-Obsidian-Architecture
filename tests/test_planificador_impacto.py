"""El planificador por impacto: selects pruebas desde el GRAFO, no por nombres.

Negativas obligatorias: si el impacto no se puede determinar con seguridad, el
plan AMPLIA o exige la suite completa. Un test no seleccionado es NOT_RUN.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audits" / "architecture"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _modulo():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "planificar_pruebas", BASE / "planificar_pruebas.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inventario_minimo():
    """Inventario y grafo pequenos y controlados para las pruebas."""
    inv = {
        "RES-MOD-A": {"id": "RES-MOD-A", "name": "modulo_a", "path": "scripts/mod_a.py",
                       "type": "modulo", "contracts": ["c1"], "invariants": ["INV-01"]},
        "RES-MOD-B": {"id": "RES-MOD-B", "name": "modulo_b", "path": "scripts/mod_b.py",
                       "type": "modulo", "contracts": ["c2"], "invariants": []},
        "RES-TST-A": {"id": "RES-TST-A", "name": "test_mod_a", "path": "tests/test_mod_a.py",
                       "type": "test", "contracts": [], "invariants": []},
        "RES-TST-B": {"id": "RES-TST-B", "name": "test_mod_b", "path": "tests/test_mod_b.py",
                       "type": "test", "contracts": [], "invariants": []},
        "RES-TST-C": {"id": "RES-TST-C", "name": "test_lejos", "path": "tests/test_lejos.py",
                       "type": "test", "contracts": [], "invariants": []},
        "RES-QG-01": {"id": "RES-QG-01", "name": "QG-01", "type": "quality gate",
                       "path": "audits/fase2/catalogo-qg.yaml", "contracts": [],
                       "invariants": []},
    }
    grafo = {"relaciones": [
        {"from": "RES-TST-A", "to": "RES-MOD-A", "relation": "VERIFIES",
         "basis": "observada", "detail": "test de mod_a"},
        {"from": "RES-TST-B", "to": "RES-MOD-B", "relation": "VERIFIES",
         "basis": "observada", "detail": "test de mod_b"},
        {"from": "RES-MOD-A", "to": "RES-QG-01", "relation": "PROVIDES",
         "basis": "observada", "detail": "la puerta ejecuta mod_a"},
    ]}
    return inv, grafo


def test_selecciona_el_test_que_verifica_el_modulo_cambiado():
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, inv, grafo)
    assert "RES-TST-A" in plan["selected_tests"]
    assert "RES-TST-B" not in plan["selected_tests"]
    assert plan["fallback_full_validation"] is False


def test_el_alcance_transitivo_llega_a_la_puerta():
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, inv, grafo)
    assert "RES-QG-01" in plan["selected_gates"]
    assert "RES-MOD-A" in plan["affected_resources"]


def test_una_dependencia_transitiva_omitida_no_pasa_desapercibida():
    """Si un modulo B depende de A y A cambia, el test de B tambien se selecciona."""
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    grafo["relaciones"].append({"from": "RES-MOD-B", "to": "RES-MOD-A",
                                "relation": "DEPENDS_ON", "basis": "declarada",
                                "detail": "B depende de A"})
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, inv, grafo)
    assert "RES-MOD-B" in plan["affected_resources"]
    assert "RES-TST-B" in plan["selected_tests"]


def test_un_cambio_sin_relaciones_exige_suite_completa():
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    plan = mod.planificar(["scripts/desconocido.py"], "a" * 40, inv, grafo)
    assert plan["fallback_full_validation"] is True
    assert plan["coverage_limitations"], plan


def test_un_grafo_con_aristas_sin_resolver_amplia_la_seleccion():
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    grafo["relaciones"].append({"from": "RES-TST-A", "to": "RES-NO-EXISTE",
                                "relation": "VERIFIES", "basis": "observada",
                                "detail": "rota"})
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, inv, grafo)
    assert plan["fallback_full_validation"] is True
    assert any("aristas" in l for l in plan["coverage_limitations"]), plan


def test_sin_inventario_se_exige_la_suite_completa():
    mod = _modulo()
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, {}, {})
    assert plan["fallback_full_validation"] is True
    assert plan["selected_tests"] == []


def test_el_plan_registra_los_tests_omitidos():
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, inv, grafo)
    assert plan["omitted_tests"] == 2  # test_mod_b y test_lejos
    assert "RES-TST-A" in plan["selected_tests"]


def test_el_plan_cumple_el_contrato():
    mod = _modulo()
    inv, grafo = _inventario_minimo()
    plan = mod.planificar(["scripts/mod_a.py"], "a" * 40, inv, grafo)
    contrato = ("plan_id", "target_sha", "source_tree", "changed_files",
                "affected_resources", "affected_contracts",
                "affected_invariants", "selected_tests", "selected_gates",
                "omitted_tests", "selection_justification",
                "coverage_limitations", "estimated_duration",
                "fallback_full_validation")
    for clave in contrato:
        assert clave in plan, clave


def test_el_plan_real_sobre_el_inventario_versionado():
    """Con el inventario real, un cambio de vault_init selecciona sus tests."""
    mod = _modulo()
    plan = mod.planificar(["scripts/vault_init.py"], "b" * 40)
    assert plan["selected_tests"], plan
    import yaml

    datos = yaml.safe_load((BASE / "inventario-maestro.yaml").read_text(
        encoding="utf-8")) or {}
    por_id = {r["id"]: r for r in datos.get("recursos", [])}
    nombres = {por_id[t]["name"] for t in plan["selected_tests"] if t in por_id}
    assert any("init" in n for n in nombres), nombres
    assert plan["selection_justification"]
