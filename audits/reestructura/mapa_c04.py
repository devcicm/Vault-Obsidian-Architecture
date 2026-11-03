#!/usr/bin/env python3
"""mapa de coste del movimiento `scripts/` → `vault/` (C-04).

Para cada módulo de `scripts/` mide lo que cuesta moverlo sin romper a nadie:

- **líneas** y si es **alias** de un dueño que ya vive en `vault/` (si lo es,
  mover no aporta nada: el código ya está en el dominio).
- **nombres públicos** que expone.
- **privados que importan los tests** — la condición del plan: un alias tiene
  que conservarlos todos.
- **fan-in**: cuántos módulos del repo lo importan.

El coste no es el tamaño: es (privados usados por tests) × (fan-in).

Uso:
    python audits/reestructura/mapa_c04.py [--markdown]
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import vault_grafo_import as gi  # noqa: E402


def _nombres(ruta: Path) -> Dict[str, List[str]]:
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return {"publicos": [], "privados": []}
    publicos, privados = [], []
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            (privados if nodo.name.startswith("_") else publicos).append(nodo.name)
        elif isinstance(nodo, ast.Assign):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name):
                    (privados if destino.id.startswith("_") else publicos).append(destino.id)
    return {"publicos": sorted(set(publicos)), "privados": sorted(set(privados))}


def _fan_in() -> Counter:
    """Cuántos módulos de `scripts/` y `vault/` importan cada módulo de `scripts/`."""
    cuenta: Counter = Counter()
    for rama in ("scripts", "vault", "tests"):
        for ruta in (REPO / rama).rglob("*.py"):
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError):
                continue
            vistos = set()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    for a in nodo.names:
                        vistos.add(a.name.split(".")[0])
                elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
                    vistos.add(nodo.module.split(".")[0])
            for modulo in vistos:
                cuenta[modulo] += 1
    return cuenta


def _privados_usados_por_tests(nombres_privados: List[str]) -> List[str]:
    """Los privados del módulo que algún test importa por nombre."""
    usados = set()
    for ruta in (REPO / "tests").glob("test_*.py"):
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                for a in nodo.names:
                    if a.name in nombres_privados:
                        usados.add(a.name)
    return sorted(usados)


def mapa() -> List[Dict[str, Any]]:
    fan_in = _fan_in()
    filas: List[Dict[str, Any]] = []
    for ruta in sorted((REPO / "scripts").glob("*.py")):
        if ruta.name.startswith("_"):
            continue
        nombres = _nombres(ruta)
        dueno = gi.codigo_de(ruta)
        alias = dueno != ruta
        filas.append({
            "modulo": ruta.stem,
            "lineas": len(ruta.read_text(encoding="utf-8", errors="replace").splitlines()),
            "alias": alias,
            "dueno": dueno.relative_to(REPO).as_posix() if alias else "",
            "publicos": len(nombres["publicos"]),
            "privados": len(nombres["privados"]),
            "privados_en_tests": _privados_usados_por_tests(nombres["privados"]),
            "fan_in": fan_in.get(ruta.stem, 0),
        })
    return filas


def _markdown(filas: List[Dict[str, Any]]) -> str:
    alias = [f for f in filas if f["alias"]]
    propios = [f for f in filas if not f["alias"]]
    costo = sorted(
        (f for f in filas if f["privados_en_tests"]),
        key=lambda f: (len(f["privados_en_tests"]) * max(1, f["fan_in"])),
        reverse=True)

    lineas = [
        "# Mapa de coste de `scripts/` → `vault/` (C-04)",
        "",
        "Instrumento: `audits/reestructura/mapa_c04.py`.",
        "",
        f"- Módulos en `scripts/`: **{len(filas)}**",
        f"- Alias de un dueño en `vault/` (mover no aporta): **{len(alias)}**",
        f"- Con código propio (candidatos a mover): **{len(propios)}**",
        f"- Con privados que algún test importa (coste real): **{len([f for f in filas if f['privados_en_tests']])}**",
        "",
        "## Los que tienen privados usados por tests, por coste",
        "",
        "| Módulo | Líneas | Públicos | Privados | Privados en tests | Fan-in | Coste |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in costo[:20]:
        coste = len(f["privados_en_tests"]) * max(1, f["fan_in"])
        lineas.append(
            f"| `{f['modulo']}` | {f['lineas']} | {f['publicos']} | {f['privados']} | "
            f"{len(f['privados_en_tests'])} | {f['fan_in']} | {coste} |")
    lineas += [
        "",
        "## Alias (el código ya vive en `vault/`)",
        "",
        "| Alias | Líneas | Dueño |",
        "|---|---|---|",
    ]
    for f in alias[:40]:
        lineas.append(f"| `{f['modulo']}` | {f['lineas']} | `{f['dueno']}` |")
    return "\n".join(lineas) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    filas = mapa()
    if "--markdown" in argv:
        print(_markdown(filas))
    else:
        print(json.dumps(filas, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
