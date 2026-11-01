#!/usr/bin/env python3
"""Higiene de los tests: lo que un test construye a mano teniendo un apoyo (AP-69).

## De dónde sale

La suite de este repo pasó de cuatro mil a casi siete mil tests escribiendo
cada fichero como si fuera el primero. Medido el 2026-10-31 sobre los 555
módulos de `tests/`: 476 `sys.path.insert` que repiten lo que el conftest ya
hace, 239 lanzadores privados de subproceso —`_run`, `_cli`, `_ejecutar`…, uno
por fichero y casi iguales—, 133 textos con varias líneas pegados con `+`, 13
`time.sleep` y un `+=` sobre una cadena dentro de un bucle. Ninguno es un fallo
por separado. El agregado es lo que hace caro el desarrollo: cada copia del
lanzador decide por su cuenta el entorno, la codificación y el timeout, y el día
que uno de los tres cambia hay 239 sitios que tocar y ninguno que lo diga.

Es AP-57 en la suite: el criterio —cómo se lanza una tool, cómo se escribe una
nota de prueba, cómo se espera a que algo pase— está reescrito por fichero.

## Qué mide

Recorre por AST los `test_*.py` de `tests/` y publica cada sitio de las clases
de `CLASES`, con su firma (`vault_firma_sitio`): mover un sitio o añadir
comentarios no lo reporta como nuevo. La baseline solo encoge; congelar deuda
nueva exige `--freeze --admitir-nuevos`, que la lista.

El apoyo que sustituye a cada clase vive en `tests/apoyo.py` y en el conftest,
que no se miden: son el sitio donde ese código debe estar.

## Qué NO demuestra el verde

- Que la suite sea rápida: eso lo mide `perfil_suite`, por módulo.
- Un lanzador que no pasa `sys.executable` (llama al binario `vault` o a
  `node`): no se ve, y se declara aquí en vez de suponerse.
- Un texto armado con `"".join` a trozos o un f-string encadenado: no es
  concatenación con `+` y no cuenta.
- `normas/*/test_*.py` queda fuera: corren con `pytest normas/` sin el conftest
  de `tests/`, y por eso sí necesitan su propio `sys.path`.

    python scripts/vault_tests_higiene.py --check --strict
    python scripts/vault_tests_higiene.py --freeze      # solo encoge
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import vault_baseline
import vault_grafo_import
from vault.kernel import rutas
from vault.meta_toolkit.estandar.firma_sitio import firmar_todos, mapa_de_qualnames
from vault_errors import emit_error, wrap_main

TOOL = "vault_tests_higiene"
BASELINE = vault_grafo_import.DIRECTORIO / "tests-higiene-baseline.json"

#: Clase -> qué se ve, qué se usa en su lugar y por qué. Lista cerrada: una
#: clase nueva entra aquí con su sustituto, o no entra.
CLASES: Dict[str, Dict[str, str]] = {
    "ruta_a_mano": {
        "ve": "sys.path.insert / sys.path.append en un módulo de test",
        "en_vez": "nada: el conftest ya pone scripts/ en el path, y "
                  "`from apoyo import ROOT, SCRIPTS` da las rutas",
        "por_que": "cada copia decide el orden del path; dos órdenes distintos "
                   "hacen que el mismo nombre importe dos módulos según qué "
                   "test corrió antes en el worker",
    },
    "lanzador_privado": {
        "ve": "una función que lanza subprocess con sys.executable",
        "en_vez": "`apoyo.correr_tool(nombre, *args, vault=, env=)`",
        "por_que": "el entorno, la codificación y el timeout del hijo se "
                   "deciden en cada copia; cambiar uno exige tocarlas todas",
    },
    "concatenacion": {
        "ve": "un texto con salto de línea pegado con `+`",
        "en_vez": "`textwrap.dedent` o `apoyo.nota(frontmatter, cuerpo)`",
        "por_que": "el texto de prueba no se lee como el fichero que fabrica, "
                   "y un salto olvidado produce un frontmatter que no es el que "
                   "el test cree estar probando",
    },
    "buffer_a_mano": {
        "ve": "`+=` sobre una cadena",
        "en_vez": "una lista y `\"\\n\".join(...)`",
        "por_que": "cuadrático en un bucle y, sobre todo, ilegible como dato",
    },
    "captura_a_mano": {
        "ve": "asignar sys.stdout / sys.stderr o redirect_stdout",
        "en_vez": "la fixture `capsys`",
        "por_que": "un test que falla antes de restaurar deja el stdout del "
                   "worker roto para todos los que vienen después",
    },
    "espera_fija": {
        "ve": "time.sleep",
        "en_vez": "esperar a la condición (con plazo) o inyectar el reloj",
        "por_que": "un sleep es a la vez lento en la máquina rápida e "
                   "insuficiente en la lenta: el test flaky más barato de escribir",
    },
}

_LANZADORES = frozenset({"run", "check_output", "check_call", "call", "Popen"})


def _es(nodo: ast.AST, modulo: str, atributo: str) -> bool:
    return (isinstance(nodo, ast.Attribute) and nodo.attr == atributo
            and isinstance(nodo.value, ast.Name) and nodo.value.id == modulo)


def _texto_con_salto(nodo: ast.AST) -> bool:
    return (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
            and "\n" in nodo.value)


def _lanza_python(funcion: ast.AST) -> bool:
    for n in ast.walk(funcion):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _LANZADORES and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "subprocess"
                and any(_es(a, "sys", "executable") for a in ast.walk(n))):
            return True
    return False


def clasificar(nodo: ast.AST) -> Optional[str]:
    """La clase de `CLASES` a la que pertenece `nodo`, o None."""
    if isinstance(nodo, ast.Call):
        f = nodo.func
        if (isinstance(f, ast.Attribute) and f.attr in ("insert", "append")
                and _es(f.value, "sys", "path")):
            return "ruta_a_mano"
        if _es(f, "time", "sleep"):
            return "espera_fija"
        if ((isinstance(f, ast.Name) and f.id == "redirect_stdout")
                or _es(f, "contextlib", "redirect_stdout")):
            return "captura_a_mano"
    if isinstance(nodo, ast.Assign) and any(
            _es(t, "sys", "stdout") or _es(t, "sys", "stderr") for t in nodo.targets):
        return "captura_a_mano"
    if (isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add)
            and (_texto_con_salto(nodo.left) or _texto_con_salto(nodo.right))):
        return "concatenacion"
    if (isinstance(nodo, ast.AugAssign) and isinstance(nodo.op, ast.Add)
            and (isinstance(nodo.value, ast.JoinedStr)
                 or (isinstance(nodo.value, ast.Constant) and isinstance(nodo.value.value, str)))):
        return "buffer_a_mano"
    if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and _lanza_python(nodo):
        return "lanzador_privado"
    return None


def sitios_de(nombre: str, texto: str) -> List[Dict[str, Any]]:
    """Los sitios de un módulo de test, firmados."""
    arbol = ast.parse(texto)
    qualnames = mapa_de_qualnames(arbol)
    hallados: List[Tuple[str, ast.AST]] = []
    for nodo in ast.walk(arbol):
        clase = clasificar(nodo)
        if clase:
            hallados.append((clase, nodo))
    # `a + "\n" + b` son dos BinOp anidados y es un solo texto: cuenta el de fuera.
    internos = {id(h) for c, n in hallados if c == "concatenacion"
                for h in ast.walk(n) if h is not n}
    hallados = sorted(((c, n) for c, n in hallados if id(n) not in internos),
                      key=lambda cn: (cn[1].lineno, cn[0]))
    firmas = firmar_todos((nombre, qualnames.get(id(n), ""), n) for _, n in hallados)
    return [{"clase": c, "firma": f"{c}::{f}", "modulo": nombre, "linea": n.lineno}
            for (c, n), f in zip(hallados, firmas)]


def sitios(directorio: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Todos los sitios de los `test_*.py` de `directorio` (por defecto, tests/)."""
    directorio = directorio or rutas.ruta_repo(rutas.TESTS)
    fuera: List[Dict[str, Any]] = []
    for ruta in sorted(directorio.glob("test_*.py")):
        try:
            fuera.extend(sitios_de(ruta.name, ruta.read_text(encoding="utf-8")))
        except SyntaxError:
            # Un test que no parsea lo rompe pytest antes que esta puerta.
            continue
    return fuera


DESCRIPCION = (
    "Sitios de tests/test_*.py que construyen a mano lo que tests/apoyo.py o el "
    "conftest ya dan (AP-69): ruta_a_mano, lanzador_privado, concatenacion, "
    "buffer_a_mano, captura_a_mano, espera_fija. Indexada por firma de sitio. "
    "Esta lista solo puede ENCOGER."
)


def _resumen(actuales: List[Dict[str, Any]]) -> Dict[str, Any]:
    por_clase = Counter(s["clase"] for s in actuales)
    por_modulo = Counter(s["modulo"] for s in actuales)
    return {
        "por_clase": {c: por_clase.get(c, 0) for c in CLASES},
        "modulos_con_deuda": len(por_modulo),
        "peores": [{"modulo": m, "sitios": n} for m, n in por_modulo.most_common(10)],
    }


def check(directorio: Optional[Path] = None, baseline: Path = BASELINE) -> Dict[str, Any]:
    actuales = sitios(directorio)
    firmas = {s["firma"] for s in actuales}
    base = vault_baseline.firmas(baseline, "sitios", "AP-69")
    nuevos, resueltos = vault_baseline.comparar(firmas, base)
    por_firma = {s["firma"]: s for s in actuales}
    return {
        "ok": not nuevos, "tool": TOOL, "norm": "AP-69", "action": "check",
        "sites_total": len(actuales), "baseline_size": len(base),
        "new_sites": [dict(por_firma[f]) for f in nuevos],
        "resolved_since_baseline": resueltos,
        **_resumen(actuales),
        "clases": CLASES,
        "hint": (
            "Se salda usando el apoyo de cada clase (`clases[*].en_vez`); un "
            "sitio resuelto se retira con `--freeze`, que solo encoge. Verde "
            "no dice que la suite sea rápida —eso es perfil_suite— sino que "
            "ningún test nuevo reescribe lo que ya tiene dueño."
        ),
    }


def freeze(admitir_nuevos: bool = False, directorio: Optional[Path] = None,
           baseline: Path = BASELINE) -> Dict[str, Any]:
    firmas = sorted({s["firma"] for s in sitios(directorio)})
    base = vault_baseline.firmas(baseline, "sitios", "AP-69")
    nuevos, _ = vault_baseline.comparar(firmas, base)
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            TOOL, "freeze", "new_sites", nuevos,
            "Usa el apoyo de su clase en vez de congelarlo. Si de verdad hay que "
            "congelar deuda nueva, `--freeze --admitir-nuevos` la lista aquí.")
    vault_baseline.escribir(baseline, "sitios", "AP-69", DESCRIPCION, firmas,
                            extra={"schema": 2})
    return {"ok": True, "tool": TOOL, "action": "freeze", "frozen": len(firmas),
            "written": 1, "admitted_new": nuevos if admitir_nuevos else []}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="vault_tests_higiene — lo que un test construye a mano teniendo apoyo (AP-69)",
        allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="publica los sitios y los nuevos")
    ap.add_argument("--strict", action="store_true", help="exit 1 si hay sitios nuevos")
    ap.add_argument("--freeze", action="store_true", help="congela lo medido; solo encoge")
    ap.add_argument("--admitir-nuevos", action="store_true",
                    help="con --freeze, congela también deuda nueva y la lista")
    args = ap.parse_args(argv)
    if args.freeze and args.check:
        r = emit_error(TOOL, "CONFLICTING_ARGS",
                       "--freeze y --check piden cosas distintas: o mide o congela",
                       pista="elige uno")
    elif args.freeze:
        r = freeze(args.admitir_nuevos)
    elif args.check:
        r = check()
    else:
        r = emit_error(TOOL, "MISSING_REQUIRED_ARG",
                       "sin --check ni --freeze esta tool no tiene nada que hacer",
                       pista="python scripts/vault_tests_higiene.py --check --strict")
    print(json.dumps(r, ensure_ascii=False))
    if r["ok"]:
        return 0
    # `--check` sin `--strict` publica la deuda nueva sin fallar; todo lo demás
    # que no sale bien —un freeze negado, unos argumentos sin sentido— es exit 1.
    return 0 if args.check and not args.strict and not args.freeze else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))
