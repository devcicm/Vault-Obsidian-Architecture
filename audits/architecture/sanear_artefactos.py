"""Sanea los artefactos publicados de la capa de arquitectura (QA-ARC-06).

Sustituye rutas de maquina por marcadores neutros. No reescribe historia ni
contenido: solo elimina identificables de lo publicado.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "audits" / "architecture"

# Rutas con usuario (larga o forma corta 8.3) y rutas absolutas de maquina.
PATRONES = [
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\"'\s)\],]+"),
    re.compile(r"[A-Za-z]:[\\/]+[A-Z0-9~]{4,8}[\\/]+[^\"'\s)\],]+"),
    re.compile(r"[A-Za-z]:[\\/]+Program Files[\\/]+[^\"'\s)\],]+"),
]

OBJETIVOS = [
    "diagnostico-escenario-a.json", "diagnostico-escenario-b.json",
    "hallazgos-qg02.yaml", "hallazgos-qg02.md",
    "divergencias-archify.yaml", "divergencias-archify.md",
    "mediciones.json", "registro-veredictos.yaml",
    "trazabilidad-qg.md", "estado-y-trazabilidad.md",
    "deuda-inconsistencias.md", "CI-EVIDENCIA.md",
    "RECONCILIACION-HISTORICA.md", "QA-RC-03-CRUZES.md",
    "ARQUITECTURA-ASIS-TOBE.md", "MATRIZ-IMPACTO.md",
]


def sanear(texto: str) -> str:
    for patron in PATRONES:
        texto = patron.sub("<RUTA-LOCAL>", texto)
    return texto


def main() -> int:
    tocados = []
    for nombre in OBJETIVOS:
        ruta = BASE / nombre
        if not ruta.is_file():
            continue
        original = ruta.read_text(encoding="utf-8", errors="replace")
        limpio = sanear(original)
        if limpio != original:
            ruta.write_text(limpio, encoding="utf-8")
            tocados.append(nombre)
    print("saneados:", tocados or "ninguno")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
