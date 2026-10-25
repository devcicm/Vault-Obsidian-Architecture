#!/usr/bin/env python3
"""Evaluador de la POLITICA de Quality Gates (R03 / H-F2-03).

El catalogo `catalogo-qg.yaml` dice QUE se exige; este modulo aplica la
POLITICA que lo hace fail-closed. Las cuatro reglas que el catalogo declaraba
en prosa y nadie ejecutaba:

  R1. QG-00 es PRERREQUISITO. Si no esta en PASS, ninguna otra puerta puede
      estar en PASS: se quedan en BLOCKED con el motivo escrito.
  R2. Sin SHA objetivo valido y sin evidencia por gate no se acredita nada:
      un estado declarado es una afirmacion, no una medicion (H-F2-04). Una
      evidencia de OTRO SHA tampoco acredita este SHA.
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

import re
from typing import Any, Dict, List

GATES = ("QG-00", "QG-01", "QG-02", "QG-03", "QG-04", "QG-05", "QG-06", "QG-07")
ESTADOS_VALIDOS = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"}
SHA_OBJETIVO = re.compile(r"^[0-9a-f]{7,40}$")

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
NOT_RUN = "NOT_RUN"


def _gate(estado: Dict[str, Any], gate: str) -> str:
    """El estado declarado de un gate; ausente = NOT_RUN (nunca PASS)."""
    valor = (estado.get("gates") or {}).get(gate, NOT_RUN)
    return valor if valor in ESTADOS_VALIDOS else NOT_RUN


def _sha_valido(estado: Dict[str, Any]) -> bool:
    """El SHA dictaminado tiene que existir y tener forma de SHA."""
    sha = estado.get("sha_objetivo")
    return isinstance(sha, str) and bool(SHA_OBJETIVO.match(sha))


def _sha_de_evidencia(estado: Dict[str, Any], gate: str) -> str | None:
    """El SHA que la evidencia del gate declara, o None si no hay evidencia."""
    evidencia = (estado.get("evidencias") or {}).get(gate)
    if not isinstance(evidencia, dict):
        return None
    sha = evidencia.get("sha")
    return sha if isinstance(sha, str) and sha else None


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
      - sha_objetivo: el SHA que se dictamina (7-40 hex; obligatorio);
      - gates: {gate: PASS|FAIL|BLOCKED|NOT_RUN|NOT_APPLICABLE} medidos;
      - evidencias: {gate: {"sha": ..., "ruta": ...}} — OBLIGATORIO para todo
        gate que pretenda PASS: sin evidencia no hay acreditacion (H-F2-04);
      - control_ejecucion: {"completo": bool, "degradados": [...],
                            "no_verificados": [...]} — opcional;
      - ci: {"conclusion": "success"|"queued"|...} — opcional.
    """
    gates: Dict[str, str] = {g: _gate(estado, g) for g in GATES}
    motivos: Dict[str, List[str]] = {g: [] for g in GATES}
    finales: Dict[str, str] = dict(gates)

    # R2: sin identidad ni evidencia no se acredita nada (H-F2-04).
    if not _sha_valido(estado):
        for gate in GATES:
            if finales[gate] == PASS:
                finales[gate] = BLOCKED
                motivos[gate].append(
                    "SHA_OBJETIVO_INVALIDO: falta un SHA de 7-40 hex a dictaminar")
    else:
        # QG-07 no se acredita con un fichero: su evidencia ES la CI, y la
        # comprueba R4 (run del SHA y conclusion). Aqui se miran QG-00..QG-06.
        for gate in GATES[:-1]:
            if finales[gate] != PASS:
                continue
            sha_evidencia = _sha_de_evidencia(estado, gate)
            if sha_evidencia is None:
                finales[gate] = BLOCKED
                motivos[gate].append(
                    "EVIDENCIA_AUSENTE: el gate no aporta evidencia con su SHA")
            elif sha_evidencia != estado["sha_objetivo"]:
                finales[gate] = BLOCKED
                motivos[gate].append(
                    "EVIDENCIA_DE_OTRO_SHA: la evidencia no pertenece al SHA "
                    "dictaminado")

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
