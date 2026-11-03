#!/usr/bin/env python3
"""inventario de subprocesos — quién lanza qué, y con qué timeout (C-06).

No es una tool del catálogo: es el instrumento con el que se decide la tanda 2
de C-2. Recorre por AST los módulos de `scripts/` y `vault/`, encuentra cada
llamada a `subprocess.run/Popen/check_output/call` y publica:

    lanzador → hijo → timeout → clase

La clase separa lo que **puede** ir en proceso de lo que no: una tool del
toolkit se puede ejecutar en este intérprete; git, node o pytest tienen su
propio contrato de proceso y no.

Uso:
    python audits/reestructura/inventario_subprocesos.py            # tabla
    python audits/reestructura/inventario_subprocesos.py --markdown  # informe
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
RAMAS = ("scripts", "vault")

#: Constantes de timeout que pueden pasarse sin número literal.
_DEFINICION_TIMEOUT = re.compile(r"^([A-Z][A-Z0-9_]*)\s*(?::\s*int\s*)?=\s*(\d+)\s*$")
_LLAMADAS = ("run", "Popen", "check_output", "check_call", "call")


def _constantes(arbol: ast.AST) -> Dict[str, str]:
    """`NOMBRE = 120` a nivel de módulo, para resolver el timeout simbólico."""
    fuera: Dict[str, str] = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            destino = nodo.targets[0]
            if isinstance(destino, ast.Name) and isinstance(nodo.value, ast.Constant):
                if isinstance(nodo.value.value, int):
                    fuera[destino.id] = str(nodo.value.value)
    return fuera


def _timeout(nodo: ast.Call, constantes: Dict[str, str]) -> Optional[str]:
    """El `timeout=` de la llamada, literal o resuelto por constante."""
    for kw in nodo.keywords:
        if kw.arg != "timeout":
            continue
        v = kw.value
        if isinstance(v, ast.Constant) and isinstance(v.value, (int, float)):
            return str(v.value)
        if isinstance(v, ast.Name) and v.id in constantes:
            return f"{v.id}={constantes[v.id]}"
        return ast.unparse(v)[:40]
    return None


def _hijo(nodo: ast.Call) -> str:
    """El hijo que se lanza, en una línea: script, módulo o comando."""
    args = nodo.args
    primero = args[0] if args else None
    texto = ast.unparse(primero)[:160] if primero is not None else ""
    # `[sys.executable, str(... / "x.py"), ...]` → el nombre del script.
    m = re.search(r'["\']([\w./-]+\.py)["\']', texto)
    if m:
        return m.group(1)
    m = re.search(r'["\']([\w./-]+\.mjs)["\']', texto)
    if m:
        return m.group(1)
    return texto


def _clase(hijo: str, texto_de_la_llamada: str) -> str:
    if "git" in hijo.split()[:1] or re.search(r'["\']git["\']', texto_de_la_llamada):
        return "git"
    if ".mjs" in hijo or re.search(r"node|npm", hijo):
        return "node"
    if "pytest" in texto_de_la_llamada:
        return "pytest"
    if ".py" in hijo or "__module__" in texto_de_la_llamada:
        return "tool" if hijo.startswith(("vault", "scripts/")) or "/vault/" in hijo else "python"
    return "otro"


def inventario() -> List[Dict[str, Any]]:
    filas: List[Dict[str, Any]] = []
    for rama in RAMAS:
        for ruta in sorted((REPO / rama).rglob("*.py")):
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            try:
                arbol = ast.parse(texto)
            except SyntaxError:
                continue
            constantes = _constantes(arbol)
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Call):
                    continue
                f = nodo.func
                nombre = f.attr if isinstance(f, ast.Attribute) else (
                    f.id if isinstance(f, ast.Name) else "")
                if nombre not in _LLAMADAS:
                    continue
                # Solo cuenta si es del módulo subprocess.
                dueño = ast.unparse(f.value) if isinstance(f, ast.Attribute) else ""
                if "subprocess" not in dueño and dueño not in ("", "sp"):
                    continue
                llamada = ast.unparse(nodo)
                hijo = _hijo(nodo)
                filas.append({
                    "lanzador": ruta.relative_to(REPO).as_posix(),
                    "linea": nodo.lineno,
                    "metodo": nombre,
                    "hijo": hijo,
                    "timeout": _timeout(nodo, constantes),
                    "clase": _clase(hijo, llamada),
                })
    return filas


def _markdown(filas: List[Dict[str, Any]]) -> str:
    sin_timeout = [f for f in filas if f["timeout"] is None]
    por_clase: Dict[str, int] = {}
    for f in filas:
        por_clase[f["clase"]] = por_clase.get(f["clase"], 0) + 1

    lineas = [
        "# Inventario de subprocesos y timeouts (C-06)",
        "",
        "Instrumento, no tool: lo genera `audits/reestructura/inventario_subprocesos.py`.",
        "",
        f"- Llamadas a `subprocess.*`: **{len(filas)}**",
        f"- Sin `timeout=`: **{len(sin_timeout)}**",
        "- Por clase: " + ", ".join(f"`{c}` {n}" for c, n in sorted(por_clase.items())),
        "",
        "## Sin timeout",
        "",
        "| Lanzador | Línea | Hijo | Clase |",
        "|---|---|---|---|",
    ]
    for f in sin_timeout:
        lineas.append(f"| `{f['lanzador']}` | {f['linea']} | `{f['hijo']}` | {f['clase']} |")
    lineas += [
        "",
        "## Todas las llamadas",
        "",
        "| Lanzador | Línea | Método | Hijo | Timeout | Clase |",
        "|---|---|---|---|---|---|",
    ]
    for f in sorted(filas, key=lambda x: (x["lanzador"], x["linea"])):
        hijo = f["hijo"].replace("|", "\\|")
        lineas.append(
            f"| `{f['lanzador']}` | {f['linea']} | {f['metodo']} | `{hijo}` | "
            f"{f['timeout'] or '—'} | {f['clase']} |")
    return "\n".join(lineas) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    filas = inventario()
    if "--markdown" in argv:
        print(_markdown(filas))
    else:
        print(json.dumps(filas, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
