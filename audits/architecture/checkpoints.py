#!/usr/bin/env python3
"""Checkpoints y observabilidad de las corridas de validacion.

Cada corrida tiene un `run_id` y un manifiesto con los eventos de la unidad
(RUN_CREATED, UNIT_STARTED, UNIT_PASSED, UNIT_FAILED, ARTIFACT_CREATED,
CHECKPOINT_SAVED, RUN_COMPLETED). Si la sesion se interrumpe, el manifiesto
sabe QUE se completo y QUE no: lo pendiente se puede repetir solo, y una
prueba interrumpida NUNCA se declara PASS.

El manifiesto vive FUERA del arbol versionado (por defecto en el directorio
temporal del usuario), para que la evidencia del candidato no dependa de si la
sesion acabo.

Uso:
    python audits/architecture/checkpoints.py iniciar --unidad "puertas" \\
        --salida <dir>
    python audits/architecture/checkpoints.py evento --salida <dir> \\
        --evento UNIT_PASSED --detalle "26/26"
    python audits/architecture/checkpoints.py estado --salida <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

EVENTOS = ("RUN_CREATED", "PLAN_GENERATED", "UNIT_STARTED", "UNIT_PASSED",
           "UNIT_FAILED", "UNIT_SKIPPED", "ARTIFACT_CREATED",
           "EVIDENCE_VERIFIED", "CHECKPOINT_SAVED", "RUN_INTERRUPTED",
           "RUN_RESUMED", "RUN_COMPLETED")


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifiesto(salida: Path) -> Path:
    return salida / "manifiesto-corrida.json"


def _cargar(salida: Path) -> Dict[str, Any]:
    ruta = _manifiesto(salida)
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def _guardar(salida: Path, datos: Dict[str, Any]) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    _manifiesto(salida).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _evento(datos: Dict[str, Any], evento: str, detalle: str = "",
            unidad: str = "", **extra: Any) -> Dict[str, Any]:
    if evento not in EVENTOS:
        raise ValueError(f"evento desconocido: {evento}")
    entrada = {"evento": evento, "timestamp": _ahora(), "unidad": unidad,
               "detalle": detalle}
    entrada.update(extra)
    datos.setdefault("eventos", []).append(entrada)
    return datos


def iniciar(salida: Path, unidad: str, sha: str = "") -> Dict[str, Any]:
    datos = _cargar(salida)
    resumed = bool(datos)
    run_id = datos.get("run_id") or f"RUN-{uuid.uuid4().hex[:12]}"
    datos.update({"run_id": run_id, "sha": sha or datos.get("sha", ""),
                  "iniciado_at": _ahora(), "estado": "EN_CURSO"})
    if resumed:
        _evento(datos, "RUN_RESUMED", "la corrida anterior quedo interrumpida",
                unidad)
    else:
        _evento(datos, "RUN_CREATED", "", unidad)
    _evento(datos, "UNIT_STARTED", "", unidad)
    _guardar(salida, datos)
    return datos


def registrar(salida: Path, evento: str, detalle: str = "", unidad: str = "",
              artefacto: str = "") -> Dict[str, Any]:
    datos = _cargar(salida)
    if not datos:
        raise SystemExit("no hay corrida: ejecuta 'iniciar' primero")
    _evento(datos, evento, detalle, unidad)
    if artefacto:
        ruta = Path(artefacto)
        _evento(datos, "ARTIFACT_CREATED",
                f"{ruta.name} sha256={_sha(ruta)}", unidad)
    datos["estado"] = "COMPLETADO" if evento == "RUN_COMPLETED" else "EN_CURSO"
    _guardar(salida, datos)
    return datos


def _sha(ruta: Path) -> str:
    import hashlib

    try:
        return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]
    except OSError:
        return "n/d"


def estado(salida: Path) -> Dict[str, Any]:
    datos = _cargar(salida)
    if not datos:
        return {"estado": "SIN_CORRIDA", "pendientes": []}
    completadas = {e["unidad"] for e in datos.get("eventos", [])
                   if e["evento"] in ("UNIT_PASSED", "UNIT_FAILED")
                   and e.get("unidad")}
    iniciadas = {e["unidad"] for e in datos.get("eventos", [])
                 if e["evento"] == "UNIT_STARTED" and e.get("unidad")}
    fallidas = {e["unidad"] for e in datos.get("eventos", [])
                if e["evento"] == "UNIT_FAILED" and e.get("unidad")}
    interrumpidas = iniciadas - completadas
    return {
        "run_id": datos.get("run_id"),
        "sha": datos.get("sha"),
        "estado": datos.get("estado"),
        "completadas": sorted(completadas - fallidas),
        "fallidas": sorted(fallidas),
        "interrumpidas": sorted(interrumpidas),
        "pendientes": sorted(interrumpidas),
        "advertencia": ("una unidad interrumpida NO es PASS: hay que repetirla"
                        if interrumpidas else ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("accion", choices=["iniciar", "evento", "estado"])
    ap.add_argument("--salida", required=True)
    ap.add_argument("--unidad", default="")
    ap.add_argument("--evento", default="")
    ap.add_argument("--detalle", default="")
    ap.add_argument("--artefacto", default="")
    ap.add_argument("--sha", default="")
    args = ap.parse_args()
    salida = Path(args.salida)
    if args.accion == "iniciar":
        print(json.dumps(iniciar(salida, args.unidad, args.sha),
                         ensure_ascii=False, indent=2))
    elif args.accion == "evento":
        print(json.dumps(registrar(salida, args.evento, args.detalle,
                                   args.unidad, args.artefacto),
                         ensure_ascii=False, indent=2))
    else:
        print(json.dumps(estado(salida), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
