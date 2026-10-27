"""El contrato PROPUESTO de certificacion compuesta (opcion C, DEC-03) es
fail-closed: cada escenario que la orden prohibe termina sin PASS, y el caso
positivo deja el residuo LISTADO (nunca silencioso).

Escenarios exigidos por el GOAL R15 §5:
  1. escape nuevo fuera del vault          -> FAIL
  2. residuo historico sin registrar       -> BLOCKED
  3. runtime con AP-39                     -> FAIL
  4. semilla del sandbox invalida          -> FAIL
  5. control obligatorio no ejecutado      -> BLOCKED
  6. control degradado / completo:false    -> BLOCKED
  7. auditoria de otro SHA                 -> BLOCKED
  8. sin auditoria de un sujeto            -> BLOCKED
  + positivo: todo limpio -> PASS con residuos (si los hay) listados.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "b" * 40


def _cargar_contrato():
    ruta = ROOT / "audits" / "fase2" / "politica_certificacion_compuesta.py"
    spec = importlib.util.spec_from_file_location(
        "politica_certificacion_compuesta", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


contrato = _cargar_contrato()


def _auditoria(violations=None, total=None, completo=True, sha=SHA):
    violations = violations or []
    return {"sha": sha,
            "total_violations": total if total is not None else len(violations),
            "violations": violations,
            "completo": completo,
            "checks": {c: "ejecutado" for c in contrato.CONTROLES_OBLIGATORIOS}}


def _evaluar(runtime=None, sandbox=None, residuos=None, historicos=None):
    return contrato.evaluar_certificacion_compuesta(
        sha_objetivo=SHA,
        auditoria_runtime=runtime if runtime is not None else _auditoria(),
        auditoria_sandbox=sandbox if sandbox is not None else _auditoria(),
        residuos_registrados=residuos or [],
        residuos_historicos_sin_decision=historicos or [])


def test_1_un_escape_nuevo_fuera_del_vault_es_fail():
    r = _evaluar(sandbox=_auditoria(violations=[
        {"id": "INC-NUEVO", "norm": "AP-36", "path": "../escape-nuevo"}]))
    assert r["estado"] == "FAIL"
    assert any("ESCAPE_NUEVO" in m for m in r["motivos"])


def test_2_un_residuo_historico_sin_registro_bloquea_y_no_pasaaa():
    r = _evaluar(
        sandbox=_auditoria(violations=[
            {"id": "INC-0001", "norm": "AP-36", "path": "../../vault-backups"}]),
        historicos=["INC-0001"])
    assert r["estado"] == "BLOCKED", "un residuo sin decision no puede pasar"
    assert any("RESIDUO_SIN_DECISION" in m for m in r["motivos"])
    # Y si ni siquiera esta catalogado como historico, es escape nuevo: FAIL.
    r2 = _evaluar(sandbox=_auditoria(violations=[
        {"id": "INC-0001", "norm": "AP-36", "path": "../../vault-backups"}]))
    assert r2["estado"] == "FAIL"


def test_3_un_runtime_con_ap39_es_fail_del_producto():
    r = _evaluar(runtime=_auditoria(violations=[
        {"id": "INC-39", "norm": "AP-39", "path": "19_Audits/vocabulary/tag-ledger.json"}]))
    assert r["estado"] == "FAIL"
    assert any("RUNTIME" in m for m in r["motivos"])


def test_4_una_semilla_de_sandbox_invalida_es_fail():
    r = _evaluar(sandbox=_auditoria(violations=[
        {"id": "INC-SEED", "norm": "CN-03", "path": "03_Decisions/adr-001.md"}]))
    assert r["estado"] == "FAIL"


def test_5_un_control_obligatorio_no_ejecutado_bloquea():
    a = _auditoria()
    a["checks"]["AP-42"] = "no_ejecutado"
    r = _evaluar(sandbox=a)
    assert r["estado"] == "BLOCKED"
    assert any("AP-42" in m for m in r["motivos"])


def test_6_un_control_degradado_o_completo_false_bloquea():
    a = _auditoria()
    a["completo"] = False
    r = _evaluar(sandbox=a)
    assert r["estado"] == "BLOCKED"
    a2 = _auditoria()
    a2["checks"]["AP-43"] = "degradado"
    r2 = _evaluar(runtime=a2)
    assert r2["estado"] == "BLOCKED"


def test_7_una_auditoria_de_otro_sha_bloquea():
    r = _evaluar(runtime=_auditoria(sha="c" * 40))
    assert r["estado"] == "BLOCKED"
    assert any("EVIDENCIA_DE_OTRO_SHA" in m for m in r["motivos"])


def test_8_sin_auditoria_de_un_sujeto_bloquea():
    r = contrato.evaluar_certificacion_compuesta(
        sha_objetivo=SHA, auditoria_runtime=None,
        auditoria_sandbox=_auditoria(), residuos_registrados=[])
    assert r["estado"] == "BLOCKED"
    assert any("sin auditoria" in m for m in r["motivos"])


def test_positivo_todo_limpio_es_pass_y_un_residuo_con_decision_queda_listado():
    # Todo limpio y SIN residuos: PASS sin asteriscos.
    r = _evaluar()
    assert r["estado"] == "PASS"
    assert r["residuos_declarados"] == []
    # Con el residuo historico YA DECIDIDO: PASS, pero el residuo queda
    # LISTADO con su decision (el PASS nunca es silencioso).
    r2 = _evaluar(
        sandbox=_auditoria(violations=[
            {"id": "INC-0001", "norm": "AP-36", "path": "../../vault-backups"}]),
        residuos=[{"id": "INC-0001",
                   "decision_ref": "DEC-04 (pendiente de firma: este caso es "
                                   "el ejemplo; sin firma real seria BLOCKED)"}])
    assert r2["estado"] == "PASS"
    assert len(r2["residuos_declarados"]) == 1
    assert r2["residuos_declarados"][0]["id"] == "INC-0001"
    assert "no es silencioso" in r2["nota"]
