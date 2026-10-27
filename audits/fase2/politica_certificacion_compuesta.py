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

Reglas (fail-closed, sin waiver):

1. RUNTIME con violaciones            -> FAIL (defecto del producto).
2. SANDBOX con un escape NO registrado y NO conocido -> FAIL (contencion
   rota: AP-36 vivo y sin expediente).
3. SANDBOX con violaciones que no sean el residuo registrado -> FAIL
   (contenido invalido, p. ej. semilla con status fuera del vocabulario).
4. RESIDUO historico sin decision -> BLOCKED (espera DEC-04; nunca PASS
   silencioso). El llamador declara cuales hallazgos son residuos historicos
   conocidos (`residuos_historicos_sin_decision`); todo hallazgo externo que
   no este ni en esa lista ni en los registrados se considera escape NUEVO.
5. RESIDUO con decision (custodia + referencia) -> el veredicto puede ser
   PASS pero el residuo queda LISTADO en la salida (registro diferenciado:
   el PASS nunca es silencioso).
6. Control obligatorio no ejecutado o degradado, o `completo: false` -> BLOCKED.
7. Evidencia de otro SHA -> BLOCKED (NEG-08: no certifica, no es defecto del
   producto).
8. Sin auditoria de alguno de los dos sujetos -> BLOCKED (NOT_RUN).

La salida SIEMPRE nombra los residuos y hallazgos que conoce, exista PASS o
no. Clases de motivo: los prefijos RUNTIME: y ESCAPE_NUEVO: son GRAVES
(FAIL); el resto (RESIDUO_SIN_DECISION:, EVIDENCIA_DE_OTRO_SHA:, controles,
completo) bloquean sin degradar a FAIL.
"""
from __future__ import annotations

from typing import Any, Dict, List

CONTROLES_OBLIGATORIOS = ("AP-40", "AP-42", "AP-43")
ESTADOS = ("PASS", "FAIL", "BLOCKED")
PREFIJOS_GRAVES = ("RUNTIME:", "ESCAPE_NUEVO:")


def _auditoria_valida(a: Dict[str, Any], nombre: str) -> List[str]:
    fallos: List[str] = []
    if not isinstance(a, dict):
        return [f"{nombre}: sin auditoria"]
    if a.get("completo") is not True:
        fallos.append(f"{nombre}: completo != true (la auditoria no pudo medir todo)")
    for control in CONTROLES_OBLIGATORIOS:
        estado = (a.get("checks") or {}).get(control)
        if estado != "ejecutado":
            fallos.append(f"{nombre}: control obligatorio {control} en estado "
                          f"{estado!r} (se exige 'ejecutado')")
    return fallos


def evaluar_certificacion_compuesta(
    *,
    sha_objetivo: str,
    auditoria_runtime: Dict[str, Any],
    auditoria_sandbox: Dict[str, Any],
    residuos_registrados: List[Dict[str, Any]],
    residuos_historicos_sin_decision: List[str] | None = None,
) -> Dict[str, Any]:
    """Veredicto de la puerta QG-02 bajo la opcion C (PROPUESTA, no aplicada).

    `residuos_registrados`: lista de residuos historicos ya tratados por el
    propietario, cada uno con al menos {"id", "decision_ref"}.
    `residuos_historicos_sin_decision`: ids de hallazgos externos conocidos
    que esperan decision (-> BLOCKED). Un hallazgo externo que no este en
    ninguna de las dos listas es un ESCAPE NUEVO -> FAIL.
    """
    motivos: List[str] = []
    residuos_en_salida: List[Dict[str, Any]] = []

    # NEG-08: la evidencia debe pertenecer al SHA objetivo (BLOCKED, no FAIL:
    # no certifica, pero no es un defecto del producto).
    for nombre, a in (("runtime", auditoria_runtime),
                      ("sandbox", auditoria_sandbox)):
        sha_evidencia = (a or {}).get("sha")
        if sha_evidencia != sha_objetivo:
            motivos.append(
                f"EVIDENCIA_DE_OTRO_SHA: la auditoria {nombre} declara sha="
                f"{sha_evidencia!r} y se examina {sha_objetivo!r}")

    # Regla 8: sin auditoria de alguno de los dos sujetos -> BLOCKED.
    faltan = [n for n, a in (("runtime", auditoria_runtime),
                             ("sandbox", auditoria_sandbox)) if not a]
    if faltan:
        return {"estado": "BLOCKED",
                "motivos": motivos + [f"sin auditoria de: {', '.join(faltan)}"],
                "residuos_declarados": residuos_en_salida}

    # Reglas 7/6: procedencia y estado de ejecucion de los controles.
    for nombre, a in (("runtime", auditoria_runtime),
                      ("sandbox", auditoria_sandbox)):
        motivos.extend(_auditoria_valida(a, nombre))

    # Regla 1: el producto se certifica sobre el runtime limpio.
    if (auditoria_runtime.get("total_violations") or 0) > 0:
        for v in auditoria_runtime.get("violations", []):
            motivos.append(f"RUNTIME: {v.get('norm')} en {v.get('path')}")
        motivos.append("RUNTIME con violaciones: defecto del producto")

    # Reglas 2-5: el sandbox, con residuos diferenciados.
    historicos = set(residuos_historicos_sin_decision or [])
    registrados_por_id = {str(r.get("id")): r for r in residuos_registrados}
    for v in auditoria_sandbox.get("violations", []):
        vid = str(v.get("id", ""))
        registro = registrados_por_id.get(vid)
        if registro is not None:
            residuos_en_salida.append({
                "id": vid,
                "norm": v.get("norm"),
                "path": v.get("path"),
                "decision_ref": registro.get("decision_ref"),
            })
        elif vid in historicos:
            motivos.append(
                f"RESIDUO_SIN_DECISION: {v.get('norm')} en {v.get('path')} "
                f"({vid} espera la decision del propietario)")
        else:
            motivos.append(
                f"ESCAPE_NUEVO: {v.get('norm')} en {v.get('path')} "
                "(sin registro ni expediente: contencion rota)")

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
                          "decision; el PASS no es silencioso y el manifiesto "
                          "de release debe llevarlos como riesgo aceptado")
    return salida
