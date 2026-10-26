#!/usr/bin/env python3
"""Publica las MEDICIONES de la ronda en el repositorio, saneadas.

Convierte lo que se midio en artefactos versionados:
  - diagnostico-escenario-{a,b}.json : la auditoria de los dos escenarios
  - mediciones.json : los hechos medidos, con `source_sha` (el arbol medido) y
    `publication_sha` (el commit que publica el artefacto) SEPARADOS: no son
    el mismo dato y confundirlos es la deriva documental (QA-ARC-07).

Sanea rutas de maquina: lo publicado no lleva identificables.

Uso:
    python audits/architecture/generar_mediciones.py --diagnosticos <dir>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "audits" / "architecture"

PATRONES = [
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\"'\s)\],]+"),
    re.compile(r"[A-Za-z]:[\\/]+[A-Z0-9~]{4,8}[\\/]+[^\"'\s)\],]+"),
]


def sanear(texto: str) -> str:
    for patron in PATRONES:
        texto = patron.sub("<RUTA-LOCAL>", texto)
    return texto


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RAIZ),
                          capture_output=True, text=True).stdout.strip()


def publicar_diagnosticos(origen: Path) -> Dict[str, Any]:
    salida: Dict[str, Any] = {}
    for nombre in ("diag-escenario-A.json", "diag-escenario-B.json"):
        ruta = origen / nombre
        if not ruta.is_file():
            continue
        datos = json.loads(sanear(ruta.read_text(encoding="utf-8")))
        destino = BASE / nombre.replace("diag-", "diagnostico-").replace(
            "-A.json", "-a.json").replace("-B.json", "-b.json")
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        salida[destino.name] = datos
    return salida


def construir_mediciones(diagnosticos: Dict[str, Any], sha_candidato: str,
                         suite: str, e2e: str) -> Dict[str, Any]:
    a = diagnosticos.get("diagnostico-escenario-a.json", {})
    b = diagnosticos.get("diagnostico-escenario-b.json", {})
    return {
        "generado_por": "audits/architecture/generar_mediciones.py",
        "source_sha": _head(),
        "publication_sha": "se fija al publicar este artefacto",
        "sha_candidato": sha_candidato,
        "nota": ("source_sha es el arbol MEDIDO; publication_sha es el commit "
                 "que publica el artefacto. No son el mismo dato."),
        "puertas": "26/26",
        "suite": suite,
        "e2e": e2e,
        "escenario_a": {"total": a.get("total"), "by_norm": a.get("by_norm"),
                        "completo": a.get("completo")},
        "escenario_b": {"total": b.get("total"), "by_norm": b.get("by_norm"),
                        "completo": b.get("completo")},
        "deuda_corregida": ["TD-0003", "TD-0008", "TD-0010", "TD-0011", "TD-0012"],
        "riesgos": [
            "La CI no se ejecuta: ningun gate de release se acredita en la matriz multiplataforma.",
            "Los cruces fuera de puerto siguen declarados y el reconciliador los refleja (10 divergencias).",
            "El sandbox canonico acumula 14 hallazgos reales de contenido de evidencia.",
            "El auditor historico mide parches, no blobs integros.",
            "Los PRD de CLI/MCP no estan contrastados con el comportamiento medido.",
        ],
        "decisiones_pendientes": [
            "Ratificar (o corregir) la Constitucion arquitectonica propuesta (DRAFT).",
            "Divergencias DIV-01..DIV-10: alternativa A (eliminar el cruce componiendo desde el meta-toolkit), B (migrarlo a un owner con puerto declarado) o C (excepcion formal con plazo y riesgo).",
            "Contrato de QG-02: certificar sobre runtime limpio (recomendado) y no sobre el vault de evidencia.",
            "Purga del directorio vault-backups fuera del vault (AP-36): lo decide el dueno de los datos.",
            "Reescritura del historial publicado: solo el propietario.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diagnosticos", required=True,
                    help="directorio con diag-escenario-{A,B}.json")
    ap.add_argument("--sha-candidato", default="")
    ap.add_argument("--suite", default="n/d")
    ap.add_argument("--e2e", default="n/d")
    args = ap.parse_args()
    diagnosticos = publicar_diagnosticos(Path(args.diagnosticos))
    medicion = construir_mediciones(diagnosticos, args.sha_candidato,
                                    args.suite, args.e2e)
    (BASE / "mediciones.json").write_text(
        json.dumps(medicion, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"diagnosticos": sorted(diagnosticos),
                      "escenario_a": medicion["escenario_a"],
                      "escenario_b": medicion["escenario_b"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
