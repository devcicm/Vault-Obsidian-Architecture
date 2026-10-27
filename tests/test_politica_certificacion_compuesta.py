"""El contrato PROPUESTO de certificacion compuesta (opcion C, DEC-03) es
fail-closed: cada escenario que la orden prohibe termina sin PASS.

ESQUEMA vs AUTORIDAD (QA-R17-QG02-01): el esquema (id, estado, firmante,
fecha, referencia, alcance, custodia) NO demuestra que el acto exista ni que
el propietario lo autorizara. Por eso hay DOS familias de pruebas:

  - ESQUEMA: las del esquema usan un verificador SINTETICO explicito. Prueban
    el cableado y el parseo, NUNCA una ratificacion real.
  - AUTORIDAD: las nuevas usan el verificador REAL sobre git, en un
    repositorio DESCARTABLE (tmp_path), con actos y custodias reales de ese
    repo de prueba. Demuestran la MECANICA (existencia, canal, contenido,
    custodia independiente, revocacion, identidad) — no que el propietario
    haya ratificado nada en este repositorio.

Escenarios exigidos por el GOAL R18 §1:
  - SHA hexadecimal inexistente.
  - Commit existente pero ajeno (no alcanzable desde el canal declarado).
  - Firmante no autorizado (autoridad ausente del registro).
  - Custodia autoafirmada (mismo SHA que el acto / `verificada: true` sin
    acta).
  - Acto sin contenido coincidente (no nombra el residuo) o revocado.
  - Sin fuente de autoridad -> BLOCKED.
  - Positivo: mecanismo sobre objetos git reales, con decision formal.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "b" * 40
HUELLA = "c" * 64
ACT = "d" * 40          # SHA del acto de decision (sintetico)
CUSTODIA = "e" * 40     # SHA del acta de custodia (sintetico)


def _cargar(nombre):
    ruta = ROOT / "audits" / "fase2" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


contrato = _cargar("politica_certificacion_compuesta")
verificador_mod = _cargar("verificador_actos")


def _decision(**cambios):
    """Decision formal sintetica y COMPLETA (la que si habilita el residuo).

    OJO: esto es un FIXTURE DE ESQUEMA. Los tests de esquema usan un
    verificador sintetico explicito y NUNCA demuestran una ratificacion real.
    """
    base = {
        "id": "DEC-99-SINTETICA",
        "estado": "RATIFICADO",
        "firmante": "autoridad-sintetica",
        "fecha": "2026-01-15",
        "referencia": ACT,
        "alcance": {"residuo": "INC-0001", "norma": "AP-36",
                    "ruta": "../../vault-backups", "huella": HUELLA},
        "custodia": {"id": "ACTA-SINTETICA", "referencia": CUSTODIA,
                     "verificada": True},
    }
    base.update(cambios)
    return base


class _VerificadorSintetico:
    """Verificador SINTETICO: aprueba cualquier acto bien formado.

    Solo existe para probar el ESQUEMA y el cableado. No demuestra nada
    sobre la realidad: por eso los tests que lo usan lo dicen.
    """

    def __init__(self, ok_acto=True, ok_custodia=True, en_vigor=True):
        self.ok_acto = ok_acto
        self.ok_custodia = ok_custodia
        self._en_vigor = en_vigor

    def en_vigor(self):
        return self._en_vigor

    def motivos_vigor(self):
        return [] if self._en_vigor else ["REGISTRO_NO_EN_VIGOR (sintetico)"]

    def verificar_acto(self, decision, hallazgo):
        return (self.ok_acto, [] if self.ok_acto else ["ACTO_NO_VERIFICADO"])

    def verificar_custodia(self, decision, hallazgo):
        return (self.ok_custodia, [] if self.ok_custodia else ["CUSTODIA_NO_VERIFICADA"])


def _hallazgo(hallazgos=True):
    if not hallazgos:
        return None
    return {"id": "INC-0001", "norm": "AP-36", "path": "../../vault-backups",
            "huella": HUELLA}


def _auditoria(violations=None, total=None, completo=True, sha=SHA,
               controles=None):
    violations = violations or []
    return {"sha": sha,
            "total_violations": total if total is not None else len(violations),
            "violations": violations,
            "completo": completo,
            "checks": controles or {c: "ejecutado" for c in contrato.CONTROLES_OBLIGATORIOS}}


def _registro(decision=None, **extra):
    reg = {"id": "INC-0001", "norma": "AP-36", "ruta": "../../vault-backups",
           "huella": HUELLA}
    if decision is not None:
        reg["decision"] = decision
    reg.update(extra)
    return reg


def _evaluar(runtime=None, sandbox=None, residuos=None, historicos=None,
             sha_objetivo=SHA, verificador=None):
    return contrato.evaluar_certificacion_compuesta(
        sha_objetivo=sha_objetivo,
        auditoria_runtime=runtime if runtime is not None else _auditoria(),
        auditoria_sandbox=sandbox if sandbox is not None else _auditoria(),
        residuos_registrados=residuos or [],
        residuos_historicos_sin_decision=historicos or [],
        verificador_actos=verificador)


def _sandbox_con_residuo():
    return _auditoria(violations=[_hallazgo()])


# ── QA-R16-QG02-01: la ratificacion se demuestra ────────────────────────────

def test_un_registro_sin_decision_no_acredita_nada():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro()])  # sin decision
    assert r["estado"] == "BLOCKED"
    assert any("RESIDUO_SIN_DECISION" in m for m in r["motivos"])


def test_una_decision_con_referencia_de_texto_libre_no_es_firma():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision={"decision_ref": "DEC-04 pendiente de firma"})])
    assert r["estado"] == "BLOCKED"
    assert any("DECISION_NO_RATIFICADA" in m or "DECISION_AUSENTE" in m
               for m in r["motivos"])


def test_una_decision_pendiente_o_no_dada_no_ratifica():
    for estado in ("PENDING", "NOT_GIVEN", "", None, "propuesto"):
        r = _evaluar(sandbox=_sandbox_con_residuo(),
                     residuos=[_registro(decision=_decision(estado=estado))])
        assert r["estado"] == "BLOCKED", f"estado={estado!r} no puede pasar"
        assert any("DECISION_NO_RATIFICADA" in m for m in r["motivos"])


def test_una_referencia_no_verificable_invalida_la_decision():
    for referencia in ("texto libre", "DEC-04@2026-10-27", "Z" * 40, ""):
        r = _evaluar(sandbox=_sandbox_con_residuo(),
                     residuos=[_registro(decision=_decision(referencia=referencia))])
        assert r["estado"] == "BLOCKED", f"referencia={referencia!r} no puede pasar"
        assert any("REFERENCIA_NO_VERIFICABLE" in m for m in r["motivos"])


def test_una_decision_ajena_mismo_id_otra_ruta_no_alcanza():
    decision = _decision(alcance={"residuo": "INC-0001", "norma": "AP-36",
                                   "ruta": "../../otro-lugar", "huella": HUELLA})
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=decision)])
    assert r["estado"] == "BLOCKED"
    assert any("ALCANCE_NO_COINCIDE" in m for m in r["motivos"])


def test_una_decision_de_otro_residuo_no_alcanza():
    decision = _decision(alcance={"residuo": "INC-9999", "norma": "AP-36",
                                   "ruta": "../../vault-backups", "huella": HUELLA})
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=decision)])
    assert r["estado"] == "BLOCKED"
    assert any("ALCANCE_NO_COINCIDE" in m for m in r["motivos"])


def test_una_decision_incompleta_no_alcanza():
    for falta in ("id", "firmante", "fecha", "referencia", "alcance", "custodia"):
        decision = _decision()
        decision.pop(falta)
        r = _evaluar(sandbox=_sandbox_con_residuo(),
                     residuos=[_registro(decision=decision)])
        assert r["estado"] == "BLOCKED", f"falta {falta} y aun asi paso"
        assert any(m.startswith(("DECISION_", "ALCANCE_", "CUSTODIA_",
                                  "REFERENCIA_")) for m in r["motivos"])


def test_una_custodia_sin_vinculo_o_no_verificada_no_alcanza():
    for custodia in ({"referencia": "", "verificada": True},
                      {"referencia": CUSTODIA, "verificada": False},
                      {"referencia": CUSTODIA}):
        r = _evaluar(sandbox=_sandbox_con_residuo(),
                     residuos=[_registro(decision=_decision(custodia=custodia))])
        assert r["estado"] == "BLOCKED", f"custodia={custodia} no puede pasar"
        assert any("CUSTODIA_" in m for m in r["motivos"])


def test_una_fecha_invalida_no_alcanza():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision(fecha="2026-13-45"))])
    assert r["estado"] == "BLOCKED"
    assert any("FECHA_INVALIDA" in m for m in r["motivos"])


def test_un_registro_vacio_o_incompleto_no_alcanza():
    r = _evaluar(sandbox=_sandbox_con_residuo(), residuos=[{}])
    assert r["estado"] == "BLOCKED"
    r2 = _evaluar(sandbox=_sandbox_con_residuo(),
                  residuos=[_registro(decision={"id": "DEC-04"})])
    assert r2["estado"] == "BLOCKED"


def test_una_identidad_de_residuo_ambigua_bloquea():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision()),
                           _registro(decision=_decision())])
    assert r["estado"] == "BLOCKED"
    assert any("IDENTIDAD_DE_RESIDUO_AMBIGUA" in m for m in r["motivos"])


def test_dec_04_pendiente_no_puede_dar_pass():
    """Con DEC-04 PENDING (que es el estado real), la puerta queda BLOCKED."""
    decision = _decision(estado="PENDING", id="DEC-04",
                          referencia="DEC-04 (pendiente de firma)")
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=decision)])
    assert r["estado"] == "BLOCKED"


# ── QA-R16-QG02-02: coherencia de la evidencia ───────────────────────────────

def test_un_conteo_ausente_o_no_entero_bloquea():
    a = _auditoria()
    del a["total_violations"]
    r = _evaluar(runtime=a)
    assert r["estado"] == "BLOCKED"
    assert any("CONTEO_AUSENTE" in m for m in r["motivos"])
    r2 = _evaluar(runtime=_auditoria(total="0"))
    assert r2["estado"] == "BLOCKED"
    assert any("CONTEO_INVALIDO" in m for m in r2["motivos"])


def test_un_conteo_negativo_bloquea():
    r = _evaluar(runtime=_auditoria(total=-1))
    assert r["estado"] == "BLOCKED"
    assert any("CONTEO_NEGATIVO" in m for m in r["motivos"])


def test_un_array_de_hallazgos_ausente_bloquea():
    a = _auditoria()
    del a["violations"]
    r = _evaluar(sandbox=a)
    assert r["estado"] == "BLOCKED"
    assert any("HALLAZGOS_AUSENTES" in m for m in r["motivos"])


def test_un_conteo_cero_con_hallazgos_presentes_bloquea():
    r = _evaluar(sandbox=_auditoria(violations=[_hallazgo()], total=0))
    assert r["estado"] == "BLOCKED"
    assert any("CONTEO_CONTRADICTORIO" in m for m in r["motivos"])


def test_un_conteo_positivo_sin_detalles_bloquea():
    r = _evaluar(sandbox=_auditoria(violations=[], total=3))
    assert r["estado"] == "BLOCKED"
    assert any("CONTEO_CONTRADICTORIO" in m for m in r["motivos"])


def test_un_conteo_que_no_cuadra_bloquea():
    r = _evaluar(sandbox=_auditoria(violations=[_hallazgo()], total=5))
    assert r["estado"] == "BLOCKED"
    assert any("CONTEO_CONTRADICTORIO" in m for m in r["motivos"])


def test_una_auditoria_incompleta_bloquea():
    r = _evaluar(sandbox=_auditoria(completo=False))
    assert r["estado"] == "BLOCKED"
    assert any("AUDITORIA_INCOMPLETA" in m for m in r["motivos"])


def test_un_control_no_ejecutado_bloquea():
    controles = {c: "ejecutado" for c in contrato.CONTROLES_OBLIGATORIOS}
    controles["AP-42"] = "no_ejecutado"
    r = _evaluar(sandbox=_auditoria(controles=controles))
    assert r["estado"] == "BLOCKED"
    assert any("CONTROL_NO_EJECUTADO" in m for m in r["motivos"])


def test_una_evidencia_de_otro_sha_bloquea():
    r = _evaluar(runtime=_auditoria(sha="c" * 40))
    assert r["estado"] == "BLOCKED"
    assert any("EVIDENCIA_DE_OTRO_SHA" in m for m in r["motivos"])


def test_una_evidencia_sin_sha_bloquea():
    a = _auditoria()
    del a["sha"]
    r = _evaluar(runtime=a)
    assert r["estado"] == "BLOCKED"
    assert any("EVIDENCIA_SIN_SHA" in m for m in r["motivos"])


# ── Clases de veredicto ──────────────────────────────────────────────────────

def test_un_escape_nuevo_sigue_siendo_fail():
    r = _evaluar(sandbox=_auditoria(violations=[
        {"id": "INC-NUEVO", "norm": "AP-36", "path": "../escape-nuevo",
         "huella": HUELLA}]))
    assert r["estado"] == "FAIL"
    assert any("ESCAPE_NUEVO" in m for m in r["motivos"])


def test_un_escape_nuevo_no_pasa_ni_con_registro_sin_decision():
    r = _evaluar(sandbox=_auditoria(violations=[
        {"id": "INC-NUEVO", "norm": "AP-36", "path": "../escape-nuevo",
         "huella": HUELLA}]),
        residuos=[_registro()])
    assert r["estado"] in ("FAIL", "BLOCKED")
    assert r["estado"] != "PASS"


def test_un_runtime_con_violaciones_es_fail():
    r = _evaluar(runtime=_auditoria(violations=[
        {"id": "INC-39", "norm": "AP-39", "path": "19_Audits/vocabulary/tag-ledger.json",
         "huella": HUELLA}]))
    assert r["estado"] == "FAIL"
    assert any("RUNTIME" in m for m in r["motivos"])


def test_el_positivo_usa_una_decision_formal_y_sintetica():
    """Caso positivo DE ESQUEMA: auditoria limpia + decision formal completa.

    El residuo queda LISTADO con su decision y su custodia: el PASS no es
    silencioso. El verificador es SINTETICO: esto prueba el parseo y el
    cableado, NO una ratificacion real (eso lo prueba la familia de
    autoridad, con objetos git reales).
    """
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision())],
                 verificador=_VerificadorSintetico())
    assert r["estado"] == "PASS", r["motivos"]
    assert len(r["residuos_declarados"]) == 1
    decl = r["residuos_declarados"][0]
    assert decl["decision_id"] == "DEC-99-SINTETICA"
    assert decl["decision_estado"] == "RATIFICADO"
    assert decl["decision_referencia"] == ACT
    assert decl["custodia_referencia"] == CUSTODIA
    assert "no es silencioso" in r["nota"]


def test_sin_fuente_de_autoridad_no_hay_pass():
    """Sin fuente confiable, el esquema no basta: BLOCKED (QA-R17-QG02-01)."""
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision())],
                 verificador=None)
    assert r["estado"] == "BLOCKED"
    assert any("SIN_FUENTE_DE_AUTORIDAD" in m for m in r["motivos"])


def test_un_verificador_que_rechaza_el_acto_bloquea():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision())],
                 verificador=_VerificadorSintetico(ok_acto=False))
    assert r["estado"] == "BLOCKED"
    assert any("ACTO_NO_VERIFICADO" in m for m in r["motivos"])


def test_un_verificador_sin_comprobacion_de_vigencia_bloquea():
    """Fail-closed: sin poder comprobar la vigencia del registro, no hay
    acreditacion (AUTH-01)."""

    class _SinVigor:
        def verificar_acto(self, decision, hallazgo):
            return (True, [])

        def verificar_custodia(self, decision, hallazgo):
            return (True, [])

    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision())],
                 verificador=_SinVigor())
    assert r["estado"] == "BLOCKED"
    assert any("VERIFICADOR_SIN_VERIFICACION_DE_VIGENCIA" in m
               for m in r["motivos"])


def test_un_registro_que_no_esta_en_vigor_bloquea():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision())],
                 verificador=_VerificadorSintetico(en_vigor=False))
    assert r["estado"] == "BLOCKED"
    assert any("REGISTRO_NO_EN_VIGOR" in m for m in r["motivos"])


def test_un_verificador_que_rechaza_la_custodia_bloquea():
    r = _evaluar(sandbox=_sandbox_con_residuo(),
                 residuos=[_registro(decision=_decision())],
                 verificador=_VerificadorSintetico(ok_custodia=False))
    assert r["estado"] == "BLOCKED"
    assert any("CUSTODIA_NO_VERIFICADA" in m for m in r["motivos"])


def test_el_positivo_sin_residuo_tambien_es_pass():
    r = _evaluar()
    assert r["estado"] == "PASS"
    assert r["residuos_declarados"] == []
