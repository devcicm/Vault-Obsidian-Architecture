"""La politica de Quality Gates (R03 / H-F2-03): reglas negativas.

Cada prueba fabrica el estado que la orden prohibe y comprueba que el
evaluador NO da PASS. El caso positivo demuestra que el PASS es alcanzable
cuando todo esta acreditado, para que el fail-closed no sea un "siempre NO".
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "audits" / "fase2"))

import politica_qg  # noqa: E402

SHA = "a" * 40
TODO_PASS = {g: "PASS" for g in politica_qg.GATES}
CONTROL_VERIFICADO = {"completo": True, "degradados": [], "no_verificados": []}


def _estado(**cambios):
    base = {
        "sha_objetivo": SHA,
        "gates": dict(TODO_PASS),
        "evidencias": {g: {"sha": SHA} for g in politica_qg.GATES},
        "control_ejecucion": dict(CONTROL_VERIFICADO),
        "ci": {"conclusion": "success"},
    }
    base.update(cambios)
    return base


def test_todo_acreditado_permite_pass():
    veredicto = politica_qg.evaluar_politica(_estado())
    assert veredicto["qg07"] == "PASS", veredicto
    assert veredicto["liberable"] is True


def test_qg00_en_fallo_bloquea_todo_lo_demas():
    """QG-00 es prerrequisito: sin identidad verificada no hay otro PASS."""
    estado = _estado()
    estado["gates"]["QG-00"] = "FAIL"
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-00"] == "FAIL"
    for gate in politica_qg.GATES[1:]:
        assert veredicto["gates"][gate] == "BLOCKED", (gate, veredicto["gates"][gate])
    assert any("PREREQUISITO_NO_CUMPLIDO:QG-00" in m
               for m in veredicto["motivos"]["QG-03"])
    assert veredicto["liberable"] is False


def test_qg02_con_control_degradado_no_da_pass():
    """26/26 puertas verdes no elimina TD-0003: un control degradado bloquea."""
    estado = _estado(control_ejecucion={
        "completo": True, "degradados": ["AP-42"]})
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-02"] == "BLOCKED", veredicto["gates"]["QG-02"]
    assert any("CONTROL_OBLIGATORIO_NO_VERIFICADO" in m
               for m in veredicto["motivos"]["QG-02"])


def test_qg02_sin_estados_de_ejecucion_es_bloqueado():
    estado = _estado(control_ejecucion={})
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-02"] == "BLOCKED"
    assert any("TD-0003" in m for m in veredicto["motivos"]["QG-02"])


def test_ci_pendiente_deja_qg07_bloqueado():
    veredicto = politica_qg.evaluar_politica(_estado(ci={"conclusion": "queued"}))
    assert veredicto["qg07"] == "BLOCKED"
    assert any("CI_PENDIENTE" in m for m in veredicto["motivos"]["QG-07"])
    assert veredicto["liberable"] is False


def test_evidencia_de_otro_sha_no_da_pass():
    estado = _estado(evidencias={g: {"sha": "b" * 40} for g in politica_qg.GATES})
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-01"] == "BLOCKED", veredicto["gates"]["QG-01"]
    assert any("EVIDENCIA_DE_OTRO_SHA" in m
               for m in veredicto["motivos"]["QG-01"])


def test_un_gate_pendiente_bloquea_qg07():
    estado = _estado()
    estado["gates"]["QG-03"] = "NOT_RUN"
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["qg07"] == "BLOCKED"
    assert any("QG_PENDIENTE:QG-03" in m for m in veredicto["motivos"]["QG-07"])


def test_not_run_nunca_es_pass():
    """Fail-closed: un gate ausente se lee NOT_RUN, jamas PASS."""
    estado = _estado()
    del estado["gates"]["QG-04"]
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-04"] == "NOT_RUN"
    assert veredicto["qg07"] == "BLOCKED"


def test_estado_invalido_se_lee_como_not_run():
    estado = _estado()
    estado["gates"]["QG-05"] = "VERDE"
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-05"] == "NOT_RUN"
