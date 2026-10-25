#!/usr/bin/env python3
"""Evaluador de la POLITICA de Quality Gates (R03 / H-F2-03).

El catalogo `catalogo-qg.yaml` dice QUE se exige; este modulo aplica la
POLITICA que lo hace fail-closed. Las cuatro reglas que el catalogo declaraba
en prosa y nadie ejecutaba:

  R1. QG-00 es PRERREQUISITO. Si no esta en PASS, ninguna otra puerta puede
      estar en PASS: se quedan en BLOCKED con el motivo escrito.
  R2. Una evidencia de OTRO SHA no acredita este SHA. El gate no puede pasar
      aunque su salida diga verde.
  R3. QG-02 no puede dar PASS con un control obligatorio no ejecutado o
      degradado: queda BLOCKED con CONTROL_OBLIGATORIO_NO_VERIFICADO. Las 26
      puertas verdes no sustituyen al estado de ejecucion (TD-0003).
  R4. QG-07 exige QG-00..QG-06 en PASS para ESE SHA y CI con conclusion. Con
      la CI en `queued` no hay veredicto: BLOCKED con CI_PENDIENTE.

Fail-closed: NOT_RUN y BLOCKED nunca se convierten en PASS; solo `success` de
la CI es conclusion valida; una entrada ausente es NOT_RUN, no PASS.

Modulo puro: no toca ficheros ni git. El llamador le pasa el estado medido.

Uso como biblioteca:
    from politica_qg import evaluar_politica
    veredicto = evaluar_politica(estado)
"""
from __future__ import annotations

from typing import Any, Dict, List

GATES = ("QG-00", "QG-01", "QG-02", "QG-03", "QG-04", "QG-05", "QG-06", "QG-07")
ESTADOS_VALIDOS = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"}

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
NOT_RUN = "NOT_RUN"


def _gate(estado: Dict[str, Any], gate: str) -> str:
    """El estado declarado de un gate; ausente = NOT_RUN (nunca PASS)."""
    valor = (estado.get("gates") or {}).get(gate, NOT_RUN)
    return valor if valor in ESTADOS_VALIDOS else NOT_RUN


def _evidencia_ajena(estado: Dict[str, Any], gate: str) -> bool:
    """True si la evidencia declarada para el gate es de OTRO SHA."""
    objetivo = estado.get("sha_objetivo")
    evidencia = (estado.get("evidencias") or {}).get(gate) or {}
    sha = evidencia.get("sha")
    if not objetivo or not sha:
        return False
    return sha != objetivo


def _ci_concluyente(estado: Dict[str, Any]) -> bool:
    """Solo `success` es conclusion; `queued`/`pending`/ausente no lo son."""
    return (estado.get("ci") or {}).get("conclusion") == "success"


def _qg02_control_verificado(estado: Dict[str, Any]) -> tuple[bool, str]:
    """QG-02 (TD-0003): el envelope tiene que declarar el estado de ejecucion.

    Sin la seccion de estados, un control obligatorio no ejecutado es
    indistinguible de uno ejecutado: esa ausencia es BLOCKED, no PASS.
    """
    control = estado.get("control_ejecucion") or {}
    if not control:
        return False, "CONTROL_OBLIGATORIO_NO_VERIFICADO: el envelope no declara el estado de ejecucion por control (TD-0003)"
    degradados = list(control.get("degradados") or [])
    no_verificados = list(control.get("no_verificados") or [])
    if degradados or no_verificados:
        detalle = sorted(set(degradados) | set(no_verificados))
        return False, f"CONTROL_OBLIGATORIO_NO_VERIFICADO: {detalle}"
    if control.get("completo") is not True:
        return False, "CONTROL_OBLIGATORIO_NO_VERIFICADO: el envelope no acredita cobertura completa"
    return True, ""


def evaluar_politica(estado: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica las reglas R1-R4 y devuelve el veredicto por gate y el de QG-07.

    `estado` es un diccionario con:
      - sha_objetivo: el SHA que se dictamina;
      - gates: {gate: PASS|FAIL|BLOCKED|NOT_RUN|NOT_APPLICABLE} medidos;
      - evidencias: {gate: {"sha": ..., "ruta": ...}} — opcional;
      - control_ejecucion: {"completo": bool, "degradados": [...],
                            "no_verificados": [...]} — opcional;
      - ci: {"conclusion": "success"|"queued"|...} — opcional.
    """
    gates: Dict[str, str] = {g: _gate(estado, g) for g in GATES}
    motivos: Dict[str, List[str]] = {g: [] for g in GATES}
    finales: Dict[str, str] = dict(gates)

    # R2: una evidencia de otro SHA no acredita este SHA.
    for gate in GATES:
        if finales[gate] == PASS and _evidencia_ajena(estado, gate):
            finales[gate] = BLOCKED
            motivos[gate].append(
                "EVIDENCIA_DE_OTRO_SHA: la evidencia no pertenece al SHA dictaminado")

    # R1: QG-00 es prerrequisito de todo lo demas.
    if finales["QG-00"] != PASS:
        for gate in GATES[1:]:
            if finales[gate] == PASS:
                finales[gate] = BLOCKED
                motivos[gate].append(
                    "PREREQUISITO_NO_CUMPLIDO:QG-00 (identidad, aislamiento y trazabilidad)")

    # R3: QG-02 no puede pasar con el control obligatorio sin verificar.
    if finales["QG-02"] == PASS:
        verificado, motivo = _qg02_control_verificado(estado)
        if not verificado:
            finales["QG-02"] = BLOCKED
            motivos["QG-02"].append(motivo)

    # R4: QG-07 exige QG-00..QG-06 en PASS y CI con conclusion.
    if finales["QG-07"] == PASS:
        pendientes = [g for g in GATES[:-1] if finales[g] != PASS]
        if pendientes:
            finales["QG-07"] = BLOCKED
            motivos["QG-07"].append(f"QG_PENDIENTE:{','.join(pendientes)}")
        elif not _ci_concluyente(estado):
            finales["QG-07"] = BLOCKED
            conclusion = (estado.get("ci") or {}).get("conclusion") or "sin dato"
            motivos["QG-07"].append(f"CI_PENDIENTE: conclusion={conclusion}")

    preparado = finales["QG-07"] == PASS
    return {
        "sha_objetivo": estado.get("sha_objetivo"),
        "gates": finales,
        "motivos": {g: m for g, m in motivos.items() if m},
        "qg07": PASS if preparado else BLOCKED,
        "liberable": preparado,
        "resumen": ("QG-07 PASS: listo para decision del propietario" if preparado
                    else "QG-07 BLOCKED: " + "; ".join(
                        motivos["QG-07"] or ["hay gates sin PASS"])),
    }


def main() -> int:
    """CLI minima: lee un JSON de estado por stdin o por argumento y evalua."""
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Evalua la politica de Quality Gates.")
    ap.add_argument("estado", nargs="?", help="JSON de estado (si se omite, stdin)")
    args = ap.parse_args()
    crudo = (Path(args.estado).read_text(encoding="utf-8") if args.estado
             else __import__("sys").stdin.read())
    veredicto = evaluar_politica(json.loads(crudo))
    print(json.dumps(veredicto, ensure_ascii=False, indent=2))
    return 0 if veredicto["liberable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
