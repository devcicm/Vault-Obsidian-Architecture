"""La politica de Quality Gates (R03 / H-F2-03): reglas negativas.

Cada prueba fabrica el estado que la orden prohibe y comprueba que el
evaluador NO da PASS. El caso positivo demuestra que el PASS es alcanzable
cuando todo esta acreditado, para que el fail-closed no sea un "siempre NO".
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def _cargar_politica_qg():
    """Carga por ruta: `audits/fase2/` no es un paquete de la suite."""
    import importlib.util

    ruta = ROOT / "audits" / "fase2" / "politica_qg.py"
    spec = importlib.util.spec_from_file_location("politica_qg", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


politica_qg = _cargar_politica_qg()

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
    assert any("CI_PENDING" in m for m in veredicto["motivos"]["QG-07"])
    assert veredicto["liberable"] is False


def test_una_ci_concluida_en_rojo_es_fallida_y_no_pendiente():
    """Un workflow que terminó con jobs rojos NO es una espera de runner.

    Medido el 2026-10-26: el candidato terminó con las cuatro columnas de
    macOS en rojo (`completed/failure`) y el veredicto lo etiquetaba como
    `CI_PENDING`, que escondía que la CI se había ejecutado y había
    fallado. La clase correcta es `CI_FAILED`; el gate sigue BLOCKED igual,
    pero el motivo dice la verdad.
    """
    veredicto = politica_qg.evaluar_politica(_estado(ci={
        "conclusion": "failure", "status": "completed",
        "detalle": "jobs_en_rojo=['Validate Vault Spec (macos-latest, 3.9)']",
    }))
    assert veredicto["gates"]["QG-07"] == "BLOCKED", veredicto["gates"]["QG-07"]
    motivos = veredicto["motivos"]["QG-07"]
    assert any("CI_FAILED" in m for m in motivos), motivos
    assert not any("CI_PENDING" in m for m in motivos), motivos
    assert any("macos-latest" in m for m in motivos), motivos


def test_una_ci_cancelada_tambien_es_fallida_y_no_pendiente():
    """Cancelada tampoco es un PASS, pero es una conclusion: no una espera."""
    veredicto = politica_qg.evaluar_politica(_estado(ci={
        "conclusion": "cancelled", "status": "completed"}))
    motivos = veredicto["motivos"]["QG-07"]
    assert any("CI_FAILED" in m for m in motivos), motivos
    assert veredicto["liberable"] is False


def test_una_ci_en_curso_es_pendiente_y_no_fallida():
    veredicto = politica_qg.evaluar_politica(_estado(ci={
        "conclusion": "", "status": "in_progress"}))
    motivos = veredicto["motivos"]["QG-07"]
    assert any("CI_PENDING" in m for m in motivos), motivos
    assert not any("CI_FAILED" in m for m in motivos), motivos


def test_sin_dato_de_ci_no_hay_pass():
    """Sin veredicto de CI, QG-07 no pasa: lo que no se mide no se presume."""
    veredicto = politica_qg.evaluar_politica(_estado(ci={}))
    assert veredicto["gates"]["QG-07"] == "BLOCKED", veredicto["gates"]["QG-07"]
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


def test_sin_sha_objetivo_no_hay_pass():
    """H-F2-04: un estado declarado sin SHA es una afirmacion, no una medicion."""
    estado = _estado()
    del estado["sha_objetivo"]
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["liberable"] is False
    assert veredicto["gates"]["QG-00"] == "BLOCKED"
    assert any("SHA_OBJETIVO_INVALIDO" in m
               for m in veredicto["motivos"]["QG-00"])


def test_sha_objetivo_vacio_o_basura_no_hay_pass():
    for malo in ("", "no-es-un-sha", "zzzzzzz", "12345"):
        estado = _estado(sha_objetivo=malo)
        veredicto = politica_qg.evaluar_politica(estado)
        assert veredicto["liberable"] is False, malo
        assert veredicto["qg07"] == "BLOCKED", malo


def test_sin_evidencias_no_hay_pass():
    """El caso exacto del dictamen: todo PASS declarado y cero evidencias."""
    estado = _estado(evidencias={})
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["liberable"] is False, veredicto
    assert veredicto["gates"]["QG-00"] == "BLOCKED"
    assert any("EVIDENCIA_AUSENTE" in m
               for m in veredicto["motivos"]["QG-00"])


def test_una_evidencia_ausente_bloquea_solo_su_gate():
    estado = _estado()
    del estado["evidencias"]["QG-03"]
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-03"] == "BLOCKED", veredicto["gates"]["QG-03"]
    assert veredicto["gates"]["QG-01"] == "PASS"
    assert veredicto["qg07"] == "BLOCKED"
    assert any("QG_PENDIENTE:QG-03" in m for m in veredicto["motivos"]["QG-07"])


def test_evidencia_sin_sha_no_acredita():
    estado = _estado()
    estado["evidencias"]["QG-04"] = {"ruta": "logs/x.txt"}
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-04"] == "BLOCKED"
    assert any("EVIDENCIA_AUSENTE" in m
               for m in veredicto["motivos"]["QG-04"])


def test_una_evidencia_de_otro_sha_bloquea_su_gate():
    estado = _estado()
    estado["evidencias"]["QG-05"] = {"sha": "b" * 40}
    veredicto = politica_qg.evaluar_politica(estado)
    assert veredicto["gates"]["QG-05"] == "BLOCKED"
    assert any("EVIDENCIA_DE_OTRO_SHA" in m
               for m in veredicto["motivos"]["QG-05"])
