#!/usr/bin/env python3
"""Planificador de pruebas por IMPACTO (pilar N1 de validacion).

Deriva del inventario maestro y del grafo que pruebas hay que ejecutar cuando
cambia un conjunto de ficheros. No es un planificador por parecido de nombres:
usa las relaciones del grafo (IMPLEMENTS, VERIFIES, CONSUMES, DEPENDS_ON).

Principio de conservadurismo: si el impacto NO se puede determinar con
seguridad, el plan AMPLIA la seleccion o exige la suite completa. Un test no
seleccionado es NOT_RUN, nunca PASS.

Contrato (audits/architecture/plan-*.yaml):
    plan_id, target_sha, source_tree, changed_files, affected_resources,
    affected_contracts, affected_invariants, selected_tests, selected_gates,
    omitted_tests, selection_justification, coverage_limitations,
    estimated_duration, fallback_full_validation

Uso:
    python audits/architecture/planificar_pruebas.py --cambios f1.py f2.py \\
        [--salida plan.yaml] [--sha SHA]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "audits" / "architecture"


def _cargar_inventario() -> Dict[str, Dict[str, Any]]:
    import yaml

    ruta = BASE / "inventario-maestro.yaml"
    if not ruta.is_file():
        return {}
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {r["id"]: r for r in datos.get("recursos", [])}


def _cargar_grafo() -> Dict[str, Any]:
    ruta = BASE / "grafo-trazabilidad.json"
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def planificar(cambios: List[str], sha: str = "",
               inventario: Dict[str, Dict[str, Any]] | None = None,
               grafo: Dict[str, Any] | None = None) -> Dict[str, Any]:
    inventario = inventario if inventario is not None else _cargar_inventario()
    grafo = grafo if grafo is not None else _cargar_grafo()
    relaciones = grafo.get("relaciones", [])
    justificaciones: List[str] = []
    limitaciones: List[str] = []

    # ── 1. recursos afectados (directos) ───────────────────────────────────
    por_ruta = {r.get("path"): rid for rid, r in inventario.items()
                if r.get("path")}
    afectados: Set[str] = set()
    for cambio in cambios:
        rid = por_ruta.get(cambio)
        if rid:
            afectados.add(rid)
    directos = len(afectados)
    if not afectados:
        limitaciones.append(
            "ningun fichero cambiado figura en el inventario: se puede "
            "afectar cualquier cosa")

    # ── 2. cierre transitivo por las relaciones del grafo ──────────────────
    # El cierre es BIDIRECCIONAL: un cambio no solo afecta a lo que el
    # recurso usa, sino a lo que lo usa (sus dependientes).
    adyacencia: Dict[str, List[str]] = {}
    inversa: Dict[str, List[str]] = {}
    for arista in relaciones:
        adyacencia.setdefault(arista["from"], []).append(arista["to"])
        inversa.setdefault(arista["to"], []).append(arista["from"])
    alcanzables: Set[str] = set(afectados)
    frontera = set(afectados)
    niveles = 0
    while frontera and niveles < 6:
        siguiente: Set[str] = set()
        for rid in frontera:
            for destino in adyacencia.get(rid, []):
                if destino not in alcanzables:
                    siguiente.add(destino)
                    alcanzables.add(destino)
            for origen in inversa.get(rid, []):
                if origen not in alcanzables:
                    siguiente.add(origen)
                    alcanzables.add(origen)
        frontera = siguiente
        niveles += 1
    if niveles >= 6:
        limitaciones.append("el cierre transitivo supero 6 niveles: impacto "
                            "potencialmente mayor que el declarado")

    # ── 3. tests seleccionados (los que VERIFICAN algo afectado) ───────────
    seleccionados: Set[str] = set()
    for arista in relaciones:
        if arista["relation"] != "VERIFIES":
            continue
        if arista["to"] in alcanzables and arista["from"] in inventario:
            recurso = inventario[arista["from"]]
            if recurso.get("type") == "test":
                seleccionados.add(arista["from"])
    # Un test que menciona el fichero cambiado tambien se selecciona: la
    # mencion es una senal mas debil, peroSelecting de mas es la parte segura.
    for rid, recurso in inventario.items():
        if recurso.get("type") != "test":
            continue
        if any(cambio.split("/")[-1].replace(".py", "") in (recurso.get("name") or "")
               or cambio.split("/")[-1] in (recurso.get("path") or "")
               for cambio in cambios):
            seleccionados.add(rid)

    # ── 4. contratos, invariantes y puertas ───────────────────────────────
    contratos = sorted({r.get("contracts", [""])[0]
                        for r in inventario.values()
                        if r["id"] in alcanzables and r.get("contracts")})
    invariantes = sorted({i for r in inventario.values()
                          if r["id"] in alcanzables for i in r.get("invariants", [])})
    puertas = sorted({r["id"] for r in inventario.values()
                      if r["id"] in alcanzables
                      and r.get("type") == "quality gate"})

    # ── 5. conservadurismo: sin relaciones, se exige la suite completa ────
    fallback = False
    if not seleccionados:
        fallback = True
        limitaciones.append("no se ha podido determinar ningun test afectado: "
                            "se exige la suite completa")
    if not inventario or not relaciones:
        fallback = True
        limitaciones.append("el inventario o el grafo no estan disponibles: "
                            "no se puede.planificar por impacto")
    if any(arista["from"] not in inventario or arista["to"] not in inventario
           for arista in relaciones):
        fallback = True
        limitaciones.append("el grafo tiene aristas sin resolver: se amplia")

    total_tests = sum(1 for r in inventario.values() if r.get("type") == "test")
    omitidos = total_tests - len(seleccionados)

    plan = {
        "plan_id": f"PLAN-{sha[:7] or 'local'}-{len(cambios)}cambios",
        "target_sha": sha,
        "source_tree": "arbol git (inmutable)",
        "changed_files": list(cambios),
        "affected_resources": sorted(alcanzables),
        "affected_contracts": contratos,
        "affected_invariants": invariantes,
        "selected_tests": sorted(seleccionados),
        "selected_gates": puertas,
        "omitted_tests": max(0, omitidos),
        "selection_justification": justificaciones + [
            f"recursos directos afectados: {directos}",
            f"cierre transitivo a {niveles} niveles: {len(alcanzables)} recursos",
            f"tests que VERIFICAN un recurso afectado: {len(seleccionados)}",
        ],
        "coverage_limitations": limitaciones,
        "estimated_duration": None,
        "fallback_full_validation": fallback,
    }
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cambios", nargs="+", required=True,
                    help="ficheros modificados (rutas relativas al repo)")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--sha", default="")
    args = ap.parse_args()
    sha = args.sha or subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RAIZ),
                                     capture_output=True, text=True).stdout.strip()
    plan = planificar(args.cambios, sha)
    texto = json.dumps(plan, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
