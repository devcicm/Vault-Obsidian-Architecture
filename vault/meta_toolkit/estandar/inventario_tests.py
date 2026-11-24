"""Inventario seccionado de módulos de test por propósito, norma y dominio.

Asigna a cada módulo `tests/test_*.py` un único bloque canónico para que
`tests/conftest.py` lo marque automáticamente en tiempo de colección. Así se
puede ejecutar un bloque puntual en segundos (`pytest -m mcp`,
`pytest -m "escritura and not slow"`, `pytest -m seguridad`) sin tocar los
ficheros de test ni perder `pytest tests/` como corrida completa única.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault.kernel import rutas
from vault.meta_toolkit.estandar import perfil_suite

#: Bloques canónicos de la suite, ordenados por dominio de producto -> estándar.
BLOQUES: Dict[str, str] = {
    "mcp": "Servidor MCP monolítico, catálogo MCP, transporte stdio/HTTP/TLS y contratos",
    "cli": "CLI de producto (`vault`), wheel, instalación limpia, portabilidad y release",
    "seguridad": "Contención AP-36, secretos, aislamiento de procesos, errores y piso Python",
    "escritura": "Write path, atomicidad, locks, políticas de mutación, historial y vcs",
    "consulta": "Búsqueda, vigencia, paquete de contexto, subgrafo, tokens y preferencias",
    "ciclo_vida": "Init, onboarding, sanación, drift, migraciones, skills y tutorial",
    "grafo": "Grafo, índices, reindexación, wikilinks, Mermaid, tags y código",
    "flujos": "Flujos y entidades de dominio (requisitos, bugs, patrones, proyectos, QA)",
    "iso": "Alineación ISO, tríada CIA, FAIR, fundamentos y calidad de datos",
    "estandar": "Normas del estándar, arquitectura interna, puertas, docs derivados y baselines",
    "integracion": "Integración transversal, orquestadores pesados y utilidades mixtas",
}

_REGLAS_DE_CLASIFICACION: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("mcp", ("mcp",)),
    ("cli", ("cli", "product", "wheel", "portab", "instal", "clean_install", "uninstall", "sbom", "release")),
    ("seguridad", ("security", "secret", "safety", "poison", "contain", "aislam", "timeout", "subproceso", "error", "blame", "excepcion", "piso_python", "filtro_de_expresiones")),
    ("escritura", ("write", "inmutab", "politica", "reglas", "frontmatter", "undo", "supersede", "delete", "trash", "quarantine", "backup", "restore", "lock", "atomic", "encoding", "history", "vcs", "git", "change_log", "bitacora")),
    ("consulta", ("search", "context", "query", "subgraph", "token", "bm25", "prefer", "ingest", "memoria", "recall", "banco_agente", "vigencia")),
    ("ciclo_vida", ("onboard", "sanacion", "drift", "migrat", "init", "upgrade", "propagate", "skill", "tutorial")),
    ("grafo", ("graph", "grafo", "link", "wiki", "bracket", "mermaid", "regex", "index", "reindex", "tag", "code_", "impact", "section")),
    ("flujos", ("req", "bug", "pattern", "patron", "flow", "project", "incident", "slo", "runbook", "qa", "flujo", "ronda", "status", "ciclo", "estado", "test_save", "dataset")),
    ("iso", ("iso", "cia", "fair", "fundament", "privacy", "riesgo", "ai_", "governance")),
    ("estandar", ("norm", "ap", "pat", "cn", "sp", "audit", "gate", "arch", "doc", "blueprint", "criterios", "clones", "kernel", "noop", "smoke", "changelog", "servicio", "voz", "voice", "baseline", "higiene", "mapa", "puente", "entorno", "contrato", "fase2", "qg", "colector", "produccion", "version", "catalogo", "inventario_tests")),
)


def clasificar_modulo(nombre: str) -> str:
    """Devuelve el bloque canónico de un módulo `test_*` (con o sin `.py`)."""
    clave = Path(nombre).stem.lower()
    for bloque, palabras in _REGLAS_DE_CLASIFICACION:
        if any(p in clave for p in palabras):
            return bloque
    return "integracion"


def resumen_inventario(
    tests_dir: Optional[Path] = None,
    pesos_ruta: Path = perfil_suite.DURACIONES,
) -> Dict[str, Any]:
    """Inventario completo por bloque con número de módulos y duración perfilada."""
    raiz = tests_dir if tests_dir is not None else rutas.ruta_repo(rutas.TESTS)
    pesos = perfil_suite.pesos(pesos_ruta)
    lentos = set(perfil_suite.lentos(pesos))
    por_bloque: Dict[str, List[str]] = defaultdict(list)

    for fichero in sorted(raiz.glob("test_*.py")):
        por_bloque[clasificar_modulo(fichero.stem)].append(fichero.stem)

    bloques: Dict[str, Dict[str, Any]] = {}
    total_modulos = 0
    total_segundos = 0.0
    for bloque, descripcion in BLOQUES.items():
        mods = por_bloque.get(bloque, [])
        segs = round(sum(pesos.get(m, 0.0) for m in mods), 1)
        mods_lentos = [m for m in mods if m in lentos]
        total_modulos += len(mods)
        total_segundos += segs
        bloques[bloque] = {
            "descripcion": descripcion,
            "modulos": len(mods),
            "segundos_perfilados": segs,
            "lentos": len(mods_lentos),
            "muestra": mods[:5],
        }

    return {
        "ok": True,
        "tool": "inventario_tests",
        "modulos_total": total_modulos,
        "segundos_perfilados_total": round(total_segundos, 1),
        "bloques": bloques,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inventario seccionado de los módulos de test por propósito",
        allow_abbrev=False,
    )
    parser.add_argument("--bloque", choices=tuple(BLOQUES), help="Lista los módulos de un bloque")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args(argv)

    if args.bloque:
        raiz = rutas.ruta_repo(rutas.TESTS)
        mods = [p.stem for p in sorted(raiz.glob("test_*.py")) if clasificar_modulo(p.stem) == args.bloque]
        payload = {"ok": True, "bloque": args.bloque, "modulos": len(mods), "lista": mods}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    resumen = resumen_inventario()
    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        for nombre, info in resumen["bloques"].items():
            print(f"{nombre:12s} | {info['modulos']:3d} modulos | {info['segundos_perfilados']:6.1f}s | lentos: {info['lentos']:2d} | {info['descripcion']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
