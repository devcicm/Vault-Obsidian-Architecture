#!/usr/bin/env python3
"""Contrato ejecutable PROPUESTO de certificacion compuesta para QG-02.

ESTADO: PROPUESTA (DEC-03). NO APLICADA. Este modulo NO toca
`catalogo-qg.yaml` ni `politica_qg.py`: es el expediente ejecutable de la
opcion C para que el propietario ratifique — o rechace — sabiendo exactamente
que haria. Sintaxis de la opcion C (GOAL R15 §5):

    El producto se certifica sobre el RUNTIME LIMPIO (lo que consume un
    tercero) y el SANDBOX CANONICO se audita contra el mismo estandar, con
    DETECCION de efectos externos nuevos y REGISTRO DIFERENCIADO de residuos
    historicos. Un residuo sin decision NUNCA se convierte silenciosamente en
    PASS: o bloquea, o queda declarado con su decision a la vista.

Reglas (fail-closed, sin waiver, sin excepcion por texto):

1. EVIDENCIA INCOHERENTE (conteo ausente/negativo, array ausente, conteo que
   no cuadra con los hallazgos, `completo: false`, control obligatorio no
   ejecutado, SHA ajeno) -> BLOCKED. Una contradiccion interna de evidencia
   jamas produce PASS ni se lee como defecto del producto.
2. RUNTIME con violaciones -> FAIL (defecto del producto).
3. ESCAPE NUEVO en el sandbox (hallazgo externo que no esta en el registro) ->
   FAIL: la contencion esta rota.
4. RESIDUO historico registrado SIN decision formal valida -> BLOCKED.
   Registrarlo no basta: la ratificacion se demuestra.
5. RESIDUO con decision formal valida -> puede coexistir con PASS, pero
   queda LISTADO por nombre (con su decision y su custodia): el PASS nunca es
   silencioso.
6. ESCAPE NUEVO nunca PASS, ni con decision, ni con registro, ni con texto.

CONTRATO DE UNA DECISION FORMAL (todo obligatorio, todo comprobable):

    "decision": {
      "id": "DEC-04",                  # identificador del acto
      "estado": "RATIFICADO",         # exacto; PENDING/NOT_GIVEN/"" no vale
      "firmante": "<autoridad>",      # quien firma
      "fecha": "YYYY-MM-DD",          # fecha del acto (ISO, parseable)
      "referencia": "<40 hex>",       # SHA inmutable del commit del acto
      "alcance": {                    # el alcance debe COINCIDIR con el
        "residuo": "INC-0001",         # hallazgo concreto: id, norma, ruta
        "norma": "AP-36",             # y huella (hash del contenido)
        "ruta": "../../vault-backups",
        "huella": "<huella del hallazgo>"
      },
      "custodia": {                   # vinculo con la custodia
        "referencia": "<40 hex>",     # SHA del acta de custodia
        "verificada": true
      }
    }

Una referencia de texto libre NO es una firma: `decision_ref: "DEC-04
(pendiente de firma...)"` no es una decision y deja la puerta BLOCKED.
"""
from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Tuple

CONTROLES_OBLIGATORIOS = ("AP-40", "AP-42", "AP-43")
ESTADOS = ("PASS", "FAIL", "BLOCKED")
PREFIJOS_GRAVES = ("RUNTIME:", "ESCAPE_NUEVO:")
ESTADO_RATIFICADO = "RATIFICADO"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _motivos_auditoria(a: Any, nombre: str) -> Tuple[List[str], bool]:
    """Coherencia de la evidencia de auditoria (QA-R16-QG02-02).

    Devuelve (motivos, coherente). Si no es coherente, la auditoria NO se
    puede usar ni para acusar al producto ni para acusar al sandbox: la
    evidencia contradictoria bloquea.
    """
    motivos: List[str] = []
    if not isinstance(a, dict):
        return ([f"{nombre}: sin auditoria (no es un objeto)"], False)

    # SHA de la evidencia (NEG-08).
    if not a.get("sha"):
        motivos.append(f"EVIDENCIA_SIN_SHA: la auditoria {nombre} no declara sha")

    # Conteo presente, entero y no negativo.
    total = a.get("total_violations", None)
    if total is None:
        motivos.append(f"CONTEO_AUSENTE: la auditoria {nombre} no declara total_violations")
    elif isinstance(total, bool) or not isinstance(total, int):
        motivos.append(f"CONTEO_INVALIDO: total_violations de {nombre} no es un entero ({total!r})")
    elif total < 0:
        motivos.append(f"CONTEO_NEGATIVO: total_violations de {nombre} es {total}")

    # Array de hallazgos presente.
    hallazgos = a.get("violations", None)
    if hallazgos is None:
        motivos.append(f"HALLAZGOS_AUSENTES: la auditoria {nombre} no declara violations")
        hallazgos = []
    elif not isinstance(hallazgos, list):
        motivos.append(f"HALLAZGOS_INVALIDOS: violations de {nombre} no es una lista")
        hallazgos = []

    # Coherencia entre el conteo y los detalles.
    if isinstance(total, int) and not isinstance(total, bool) and total >= 0 \
            and isinstance(a.get("violations"), list):
        if total == 0 and hallazgos:
            motivos.append(
                f"CONTEO_CONTRADICTORIO: {nombre} declara 0 violaciones y lista "
                f"{len(hallazgos)}")
        elif total > 0 and not hallazgos:
            motivos.append(
                f"CONTEO_CONTRADICTORIO: {nombre} declara {total} violaciones y "
                "no lista ninguna")
        elif total != len(hallazgos):
            motivos.append(
                f"CONTEO_CONTRADICTORIO: {nombre} declara {total} violaciones y "
                f"lista {len(hallazgos)}")

    # Integridad de la ejecucion.
    if a.get("completo") is not True:
        motivos.append(f"AUDITORIA_INCOMPLETA: {nombre} no declara completo=true")
    for control in CONTROLES_OBLIGATORIOS:
        estado = (a.get("checks") or {}).get(control)
        if estado != "ejecutado":
            motivos.append(
                f"CONTROL_NO_EJECUTADO: {nombre} declara {control} en estado "
                f"{estado!r} (se exige 'ejecutado')")
    return (motivos, not motivos)


def _motivos_decision(decision: Any, hallazgo: Dict[str, Any]) -> List[str]:
    """Decision formal de un residuo (QA-R16-QG02-01).

    Una decision se acepta solo si es un objeto con los SEIS requisitos del
    contrato y su alcance COINCIDE con el hallazgo. Cualquier fallo -> el
    residuo queda sin ratificar (BLOCKED).
    """
    motivos: List[str] = []
    if not isinstance(decision, dict) or not decision:
        return ["DECISION_AUSENTE: el residuo registrado no lleva decision formal"]

    if not str(decision.get("id") or "").strip():
        motivos.append("DECISION_SIN_IDENTIFICADOR")
    if decision.get("estado") != ESTADO_RATIFICADO:
        motivos.append(
            f"DECISION_NO_RATIFICADA: estado={decision.get('estado')!r} "
            f"(se exige {ESTADO_RATIFICADO!r}; PENDING/NOT_GIVEN/vacio no valen)")
    firmante = decision.get("firmante")
    if not isinstance(firmante, str) or not firmante.strip():
        motivos.append("DECISION_SIN_FIRMANTE")
    fecha = decision.get("fecha")
    if (not isinstance(fecha, str) or not FECHA_RE.match(fecha)):
        motivos.append(f"DECISION_CON_FECHA_INVALIDA: {fecha!r} (se exige YYYY-MM-DD)")
    else:
        try:
            datetime.date.fromisoformat(fecha)
        except ValueError:
            motivos.append(f"DECISION_CON_FECHA_INVALIDA: {fecha!r} no es una fecha real")
    referencia = decision.get("referencia")
    if not isinstance(referencia, str) or not SHA_RE.match(referencia):
        motivos.append(
            f"REFERENCIA_NO_VERIFICABLE: {referencia!r} no es un SHA inmutable "
            "(40 hex): una referencia de texto libre no es una firma")

    # Alcance: debe identificar ESTE hallazgo (id, norma, ruta y huella).
    # El hallazgo se normaliza: usa `norm`/`path`; el contrato, `norma`/`ruta`.
    esperado = {
        "residuo": hallazgo.get("id"),
        "norma": hallazgo.get("norm", hallazgo.get("norma")),
        "ruta": hallazgo.get("path", hallazgo.get("ruta")),
        "huella": hallazgo.get("huella"),
    }
    alcance = decision.get("alcance")
    if not isinstance(alcance, dict):
        motivos.append("ALCANCE_AUSENTE")
    else:
        for campo in ("residuo", "norma", "ruta", "huella"):
            valor = esperado[campo]
            if valor is None:
                motivos.append(f"HUELLA_O_IDENTIDAD_AUSENTE: el hallazgo no declara {campo}")
                continue
            if alcance.get(campo) != valor:
                motivos.append(
                    f"ALCANCE_NO_COINCIDE: {campo} de la decision "
                    f"({alcance.get(campo)!r}) no es el del hallazgo ({valor!r})")

    # Custodia: vinculo verificable con el acto de custodia.
    custodia = decision.get("custodia")
    if not isinstance(custodia, dict):
        motivos.append("CUSTODIA_NO_VINCULADA: la decision no aporta custodia")
    else:
        ref_custodia = custodia.get("referencia")
        if not isinstance(ref_custodia, str) or not ref_custodia.strip():
            motivos.append("CUSTODIA_SIN_REFERENCIA")
        if custodia.get("verificada") is not True:
            motivos.append("CUSTODIA_NO_VERIFICADA")
    return motivos


def evaluar_certificacion_compuesta(
    *,
    sha_objetivo: str,
    auditoria_runtime: Dict[str, Any],
    auditoria_sandbox: Dict[str, Any],
    residuos_registrados: List[Dict[str, Any]],
    residuos_historicos_sin_decision: List[str] | None = None,
) -> Dict[str, Any]:
    """Veredicto de la puerta QG-02 bajo la opcion C (PROPUESTA, no aplicada).

    `residuos_registrados`: residuos historicos ya tratados por el propietario.
    Cada entrada declara la identidad del hallazgo (id, norma, ruta, huella) y
    su `decision` formal (ver el contrato del modulo). Un registro SIN decision
    formal valida NO acredita nada: el residuo queda BLOCKED.
    """
    motivos: List[str] = []
    residuos_en_salida: List[Dict[str, Any]] = []

    # Regla 1 (primero): coherencia de la evidencia. Sin coherencia, los
    # hallazgos no se usan ni para FAIL ni para PASS.
    motivos_runtime, coherente_runtime = _motivos_auditoria(auditoria_runtime, "runtime")
    motivos_sandbox, coherente_sandbox = _motivos_auditoria(auditoria_sandbox, "sandbox")
    motivos.extend(motivos_runtime)
    motivos.extend(motivos_sandbox)
    if not (coherente_runtime and coherente_sandbox):
        return {"estado": "BLOCKED", "motivos": motivos,
                "residuos_declarados": residuos_en_salida,
                "nota": "evidencia incoherente o incompleta: no se evalua el "
                        "merito; se bloquea"}

    # Evidencia de otro SHA (NEG-08) — ya detectado arriba como SHA ausente;
    # aqui se comprueba la coincidencia con el objetivo.
    for nombre, a in (("runtime", auditoria_runtime), ("sandbox", auditoria_sandbox)):
        if a.get("sha") != sha_objetivo:
            motivos.append(
                f"EVIDENCIA_DE_OTRO_SHA: la auditoria {nombre} declara sha="
                f"{a.get('sha')!r} y se examina {sha_objetivo!r}")
    if motivos:
        return {"estado": "BLOCKED", "motivos": motivos,
                "residuos_declarados": residuos_en_salida,
                "nota": "la evidencia no pertenece al SHA examinado"}

    # Identidad ambigua: el mismo id de residuo registrado dos veces, y
    # registros mal formados (sin id) — el registro no identifica de forma
    # univoca que se ratifico, y la evidencia no es de fiar.
    ids = [str(r.get("id")) for r in residuos_registrados if isinstance(r, dict)]
    duplicados = sorted({i for i in ids if ids.count(i) > 1})
    if duplicados:
        return {"estado": "BLOCKED",
                "motivos": [f"IDENTIDAD_DE_RESIDUO_AMBIGUA: ids repetidos en el "
                            f"registro: {duplicados}"],
                "residuos_declarados": residuos_en_salida,
                "nota": "el registro de residuos no identifica de forma univoca "
                        "que se ratifico"}
    sin_id = [str(r) for r in residuos_registrados
              if not isinstance(r, dict) or not str(r.get("id") or "").strip()]
    if sin_id:
        return {"estado": "BLOCKED",
                "motivos": [f"REGISTRO_INVALIDO: entradas sin id utilizable: {sin_id}"],
                "residuos_declarados": residuos_en_salida,
                "nota": "el registro de residuos esta mal formado"}

    registrados_por_id = {str(r.get("id")): r for r in residuos_registrados}
    historicos = set(residuos_historicos_sin_decision or [])

    # Regla 2: el producto se certifica sobre el runtime limpio.
    if auditoria_runtime.get("total_violations"):
        for v in auditoria_runtime.get("violations", []):
            motivos.append(f"RUNTIME: {v.get('norm')} en {v.get('path')}")
        motivos.append("RUNTIME con violaciones: defecto del producto")

    # Reglas 3-6: el sandbox, con residuos diferenciados.
    for v in auditoria_sandbox.get("violations", []):
        vid = str(v.get("id", ""))
        registro = registrados_por_id.get(vid)
        if registro is None:
            if vid in historicos:
                motivos.append(
                    f"RESIDUO_SIN_DECISION: {v.get('norm')} en {v.get('path')} "
                    f"({vid} espera la decision del propietario)")
            else:
                motivos.append(
                    f"ESCAPE_NUEVO: {v.get('norm')} en {v.get('path')} "
                    "(sin registro ni expediente: contencion rota)")
            continue
        fallos = _motivos_decision(registro.get("decision"), v)
        # El REGISTRO tiene que apuntar a ESTE hallazgo (mismo id, misma
        # norma, misma ruta, misma huella): un registro del mismo id para
        # otra ruta es un registro de otro residuo.
        identidad_registro = {
            "norma": registro.get("norma", registro.get("norm")),
            "ruta": registro.get("ruta", registro.get("path")),
            "huella": registro.get("huella"),
        }
        identidad_hallazgo = {
            "norma": v.get("norm", v.get("norma")),
            "ruta": v.get("path", v.get("ruta")),
            "huella": v.get("huella"),
        }
        for campo in ("norma", "ruta", "huella"):
            if identidad_registro.get(campo) != identidad_hallazgo.get(campo):
                fallos.append(
                    f"REGISTRO_NO_COINCIDE_CON_HALLAZGO: {campo} del registro "
                    f"({identidad_registro.get(campo)!r}) no es el del hallazgo "
                    f"({identidad_hallazgo.get(campo)!r})")
        if fallos:
            # Cada motivo se expone POR SEPARADO (con el residuo como
            # contexto): una consumer puede clasificar cada uno sin tener que
            # parsear una frase.
            motivos.append(
                f"RESIDUO_SIN_DECISION: {vid} esta registrado pero su decision "
                "no es formal:")
            for fallo in fallos:
                motivos.append(f"{fallo} (residuo {vid})")
            continue
        decision = registro["decision"]
        residuos_en_salida.append({
            "id": vid,
            "norma": v.get("norm"),
            "ruta": v.get("path"),
            "huella": v.get("huella"),
            "decision_id": decision.get("id"),
            "decision_estado": decision.get("estado"),
            "decision_firmante": decision.get("firmante"),
            "decision_fecha": decision.get("fecha"),
            "decision_referencia": decision.get("referencia"),
            "custodia_referencia": (decision.get("custodia") or {}).get("referencia"),
        })

    graves = [m for m in motivos if m.startswith(PREFIJOS_GRAVES)]
    if graves:
        estado = "FAIL"
    elif motivos:
        estado = "BLOCKED"
    else:
        estado = "PASS"

    salida = {"estado": estado, "motivos": motivos,
              "residuos_declarados": residuos_en_salida}
    if estado == "PASS":
        salida["nota"] = ("los residuos listados quedan declarados con su "
                          "decision formal y su custodia; el PASS no es "
                          "silencioso y el manifiesto de release debe llevarlos "
                          "como riesgo aceptado")
    return salida
