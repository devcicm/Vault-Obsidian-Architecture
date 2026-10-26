#!/usr/bin/env python3
"""Clasificación de la suite en PIRÁMIDE DE VALIDACIÓN L0-L3 (medida, no estimada).

Fuente: el JUnit XML de una corrida real (`--junit`), que trae el tiempo de cada
caso. El nivel de un fichero de test sale de la MEDIANA del tiempo por caso:

    L0 sanidad:     < 1 s      (función pura, sin I/O)
    L1 unidad:      < 5 s      (un módulo, ficheros temporales propios)
    L2 integración: < 30 s     (subprocesos, CLI, puertas, vaults temporales)
    L3 extremo:    >= 30 s     (viajes completos, gates enteros, E2E, descubrimiento)

Los límites son una convención declarada aquí (no un hallazgo): lo medido es el
tiempo y los conteos; lo convencional es el corte. Cualquier cambio de corte se
propaga a todo el documento derivado.

Salidas (ambas derivadas, regenerar con este script):
  - audits/architecture/piramide-niveles.json  (fichero -> nivel, casos, tiempo)
  - audits/architecture/PIRAMIDE-VALIDACION.md (documento derivado)

Uso:
    python audits/architecture/piramide_validacion.py --junit <ruta> \
        [--pared SEGUNDOS]   # reloj real de la corrida, para el factor de paralelismo
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "audits" / "architecture"

NIVELES = ("L0", "L1", "L2", "L3")
NOMBRE_NIVEL = {"L0": "sanidad", "L1": "unidad", "L2": "integración",
                "L3": "extremo"}
CORTES = {"L0": 1.0, "L1": 5.0, "L2": 30.0}


def nivel_de_mediana(mediana: float) -> str:
    if mediana < CORTES["L0"]:
        return "L0"
    if mediana < CORTES["L1"]:
        return "L1"
    if mediana < CORTES["L2"]:
        return "L2"
    return "L3"


def leer_junit(ruta: Path) -> list[dict]:
    if not ruta.is_file():
        raise SystemExit(f"no existe el JUnit: {ruta}")
    raiz = ET.parse(str(ruta)).getroot()
    suites = [raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite")
    casos = []
    for suite in suites:
        for tc in suite.findall("testcase"):
            clase = tc.get("classname") or ""
            casos.append({
                "tiempo": float(tc.get("time") or 0),
                "fichero": clase.split(".")[-1] if clase else "",
            })
    return casos


def clasificar(casos: list[dict]) -> dict:
    por_fichero: dict[str, list[float]] = collections.defaultdict(list)
    for c in casos:
        if c["fichero"]:
            por_fichero[c["fichero"]].append(c["tiempo"])
    fichas = []
    for nombre, tiempos in por_fichero.items():
        # mediana de CASO (no suma): un fichero con 40 casos de 0,5 s y uno de
        # 150 s sigue siendo un fichero de unidad con un viaje dentro.
        mediana = statistics.median(tiempos)
        fichas.append({
            "fichero": nombre,
            "nivel": nivel_de_mediana(mediana),
            "casos": len(tiempos),
            "mediana_caso": round(mediana, 3),
            "max_caso": round(max(tiempos), 2),
            "total": round(sum(tiempos), 2),
        })
    return {
        "fuente": "JUnit de una corrida real",
        "cortes_por_caso": CORTES,
        "ficheros": sorted(fichas, key=lambda f: -f["total"]),
    }


def construir_doc(datos: dict, pared: float | None) -> str:
    """Documento derivado: cada cifra sale de `datos`, ninguna a mano."""
    por_nivel: dict[str, dict] = {n: {"ficheros": 0, "casos": 0, "total": 0.0}
                                  for n in NIVELES}
    for f in datos["ficheros"]:
        n = por_nivel[f["nivel"]]
        n["ficheros"] += 1
        n["casos"] += f["casos"]
        n["total"] += f["total"]
    total = sum(n["total"] for n in por_nivel.values()) or 1.0

    lineas = [
        "# Pirámide de validación (medida)",
        "",
        f"Fuente: `{datos['fuente']}`. Nivel de un fichero de test = mediana del",
        "tiempo por caso. Cortes (convención declarada):",
        "L0 < 1s · L1 < 5s · L2 < 30s · L3 >= 30s (mediana por caso).",
        "",
        "| Nivel | Significa | Ficheros | Casos | Suma de tiempos | % del total |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for n in NIVELES:
        d = por_nivel[n]
        lineas.append(f"| {n} | {NOMBRE_NIVEL[n]} | {d['ficheros']} "
                      f"| {d['casos']} | {d['total']:.1f}s "
                      f"| {100 * d['total'] / total:.1f}% |")
    lineas.append(f"| total | — | {sum(n['ficheros'] for n in por_nivel.values())} "
                  f"| {sum(n['casos'] for n in por_nivel.values())} "
                  f"| {total:.1f}s | 100% |")

    if pared:
        factor = total / pared if pared else 0
        lineas += ["",
                   f"Reloj real de la corrida: {pared:.0f}s contra {total:.0f}s "
                   f"de suma de casos → factor de paralelismo {factor:.1f}×."]

    # El extremo de la distribución, por fichero: donde vive el coste.
    lentos = [f for f in datos["ficheros"] if f["nivel"] == "L3"][:10]
    lineas += ["", "## El extremo L3 (ficheros whose mediana supera el corte)", "",
               "Estos dominan el coste total; son la cola que el carril rápido",
               "evita y la que conviene revisar primero (identificados por su",
               "nombre, no por estimación):", ""]
    for f in lentos:
        lineas.append(f"- `{f['fichero']}` — {f['casos']} casos, mediana "
                      f"{f['mediana_caso']:.1f}s, total {f['total']:.0f}s")

    # Los casos únicos más caros: viajes largos dentro de ficheros de mediana
    # baja (la mediana por fichero NO los ve; son duplicación de gates o E2E
    # interno y el coste real del carril completo).
    por_caso = sorted(datos["ficheros"], key=lambda f: -f["max_caso"])[:10]
    lineas += ["", "## Los 10 casos únicos más caros (mediana los esconde)", "",
               "Un solo caso largo dentro de un fichero de unidad es el patrón",
               "de 'gate completo dentro de un test': el carril rápido lo evita",
               "igual, pero la revisión del harness debe verlo:", ""]
    for f in por_caso:
        if f["max_caso"] < 30:
            break
        lineas.append(f"- `{f['fichero']}` — caso más caro "
                      f"{f['max_caso']:.0f}s (mediana del fichero "
                      f"{f['mediana_caso']:.1f}s, nivel {f['nivel']})")

    # Carril rápido: los L0+L1 primero.
    rapido = por_nivel["L0"]["casos"] + por_nivel["L1"]["casos"]
    todos = sum(n["casos"] for n in por_nivel.values()) or 1
    t_rapido = por_nivel["L0"]["total"] + por_nivel["L1"]["total"]
    lineas += ["", "## Carril rápido",
               "",
               f"L0+L1 cubren {rapido} casos de {todos} "
               f"({100 * rapido / todos:.1f}%) con {t_rapido:.0f}s de suma sobre "
               f"{total:.0f}s ({100 * t_rapido / total:.1f}%): es el carril para",
               "iterar; NO sustituye al cierre completo.",
               "",
               "Duplicaciones detectadas con medición (gates ejecutados dentro",
               "de tests): viven en la lista del extremo L3 — su coste es la",
               "señal; el criterio de desduplicación lo decide la revisión del",
               "harness, no este documento."]
    return "\n".join(lineas) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--junit", required=True)
    ap.add_argument("--pared", type=float, default=None,
                    help="reloj real de la corrida en segundos")
    ap.add_argument("--salida-json", default=str(BASE / "piramide-niveles.json"))
    ap.add_argument("--salida-md", default=str(BASE / "PIRAMIDE-VALIDACION.md"))
    args = ap.parse_args()

    casos = leer_junit(Path(args.junit))
    datos = clasificar(casos)
    Path(args.salida_json).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc = construir_doc(datos, args.pared)
    Path(args.salida_md).write_text(doc, encoding="utf-8")
    por_nivel = collections.Counter(f["nivel"] for f in datos["ficheros"])
    print(json.dumps({"ficheros": len(datos["ficheros"]),
                      "por_nivel": dict(por_nivel)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
