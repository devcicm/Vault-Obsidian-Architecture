"""El piso de Python que se promete es el piso que se cumple.

`pyproject.toml` declara `requires-python = ">=3.9"` y la CI prueba **una sola
versión, 3.11**. Es la misma forma de defecto que ocupó toda v40.30: un alcance
declarado más ancho que el alcance que de verdad se recorre. Y no daba un error
—daba un verde—, porque la única máquina que ejecutaba el toolkit tenía de sobra.

Medido al preguntarse si otra persona puede usar esto: **seis sitios rompían en
3.9**, dos de ellos en `vault_grafo_import` (dueño del grafo del que AP-59
deriva sus umbrales) y `vault_norms_catalog` (el catálogo que importa medio
repo). No fallaban al llamarse: fallaban al **importar el módulo**, porque
`ast.AST | None` en una anotación se evalúa al definir la función si el módulo
no trae `from __future__ import annotations`. En 3.9 eso es un `TypeError` y el
toolkit entero no arranca.

Este test no comprueba «que funcione en 3.9»: para eso hace falta un intérprete
3.9, y eso es trabajo de la CI. Comprueba las dos cosas que sí se pueden medir
desde cualquier versión, y **declara lo que no ve** en vez de dar la promesa por
cumplida.
"""

from __future__ import annotations

import ast
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent

#: Stdlib posterior a 3.9. Nombre -> versión que lo estrenó. Se amplía cuando
#: alguien tropiece con uno nuevo; no pretende ser exhaustivo y por eso el
#: docstring lo dice.
POSTERIORES_A_39 = {
    "tomllib": "3.11", "itertools.pairwise": "3.10", "typing.Self": "3.11",
    "datetime.UTC": "3.11", "asyncio.TaskGroup": "3.11", "enum.StrEnum": "3.11",
    "hashlib.file_digest": "3.11", "typing.TypeAlias": "3.10",
    "typing.ParamSpec": "3.10", "contextlib.chdir": "3.11",
    "typing.override": "3.12", "itertools.batched": "3.12",
    "typing.TypeIs": "3.13",
}

EXCLUIDOS = (".git", "vault-sandbox", "node_modules", ".venv")


def piso_declarado() -> tuple[int, int]:
    """El piso sale de `pyproject.toml`, nunca de una constante de este fichero.

    Escribirlo aquí sería AP-47: dos sitios diciendo qué versión se soporta, y
    el test pasando en verde mientras el paquete promete otra cosa.
    """
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'requires-python\s*=\s*"[><=~^]*\s*(\d+)\.(\d+)', texto)
    assert m, "pyproject.toml no declara requires-python"
    return int(m.group(1)), int(m.group(2))


def _ficheros() -> list[pathlib.Path]:
    return [
        p for p in sorted(RAIZ.rglob("*.py"))
        if not any(x in p.parts for x in EXCLUIDOS)
    ]


def test_la_sintaxis_cabe_en_el_piso_declarado():
    """`match`, `except*` y los genéricos de PEP 695 no existen en 3.9."""
    piso = piso_declarado()
    culpables = []
    for ruta in _ficheros():
        try:
            ast.parse(ruta.read_text(encoding="utf-8", errors="replace"),
                      feature_version=piso)
        except SyntaxError as e:
            culpables.append(f"{ruta.relative_to(RAIZ).as_posix()}:{e.lineno}: {e.msg}")
    assert not culpables, (
        f"sintaxis que Python {piso[0]}.{piso[1]} no acepta, y pyproject.toml "
        f"promete soportarlo:\n  " + "\n  ".join(culpables)
    )


def test_ninguna_anotacion_pep604_se_evalua_al_definir():
    """`int | None` es sintaxis válida siempre y `TypeError` al ejecutarse.

    Por eso ningún parser lo ve y por eso rompía al **importar**, que es el
    momento más caro: no cae la función que lo usa, cae el módulo entero y con
    él todo lo que dependa de él.

    La cura es una línea, `from __future__ import annotations`, que difiere la
    evaluación. Se exige el `__future__` y no se prohíbe el `|`: prohibirlo
    obligaría a escribir `Optional[...]` en código nuevo por una versión que
    quizá nadie use, y esa decisión es del dueño del paquete, no de un test.
    """
    if piso_declarado() >= (3, 10):
        return  # desde 3.10 la evaluación diferida ya no hace falta
    culpables = []
    for ruta in _ficheros():
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        if any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
               and any(a.name == "annotations" for a in n.names)
               for n in arbol.body):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            anotaciones = [a.annotation for a in nodo.args.args if a.annotation]
            anotaciones += [a.annotation for a in nodo.args.kwonlyargs if a.annotation]
            if nodo.returns:
                anotaciones.append(nodo.returns)
            for anot in anotaciones:
                if any(isinstance(s, ast.BinOp) and isinstance(s.op, ast.BitOr)
                       for s in ast.walk(anot)):
                    culpables.append(
                        f"{ruta.relative_to(RAIZ).as_posix()}:{nodo.lineno}: {nodo.name}()")
                    break
    assert not culpables, (
        "anotación PEP 604 evaluada al definir, en un módulo sin "
        "`from __future__ import annotations`. Rompe al IMPORTAR en Python 3.9:"
        "\n  " + "\n  ".join(sorted(set(culpables)))
    )


def test_ninguna_api_de_stdlib_es_posterior_al_piso():
    """Lo que no ve ningún parser: una función que no existía en 3.9.

    Alcance declarado: solo los nombres de `POSTERIORES_A_39`, y solo escritos
    literalmente. Una API alcanzada por `getattr` o por un nombre construido no
    la ve, igual que `vault_criterios` declara que no ve la copia sintáctica.
    """
    piso = piso_declarado()
    culpables = []
    for ruta in _ficheros():
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        rel = ruta.relative_to(RAIZ).as_posix()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.Import, ast.ImportFrom)):
                nombres = [a.name for a in nodo.names]
                if isinstance(nodo, ast.ImportFrom) and nodo.module:
                    nombres.append(nodo.module)
                for n in nombres:
                    v = POSTERIORES_A_39.get(n.split(".")[0])
                    if v and tuple(int(x) for x in v.split(".")) > piso:
                        culpables.append(f"{rel}:{nodo.lineno}: import {n} (desde {v})")
            elif isinstance(nodo, ast.Attribute):
                try:
                    nombre = ast.unparse(nodo)
                except Exception:
                    continue
                v = POSTERIORES_A_39.get(nombre)
                if v and tuple(int(x) for x in v.split(".")) > piso:
                    culpables.append(f"{rel}:{nodo.lineno}: {nombre} (desde {v})")
    assert not culpables, "\n  ".join(sorted(set(culpables)))


def test_la_ci_prueba_el_piso_que_se_promete():
    """Un piso que ninguna máquina ejecuta es una promesa, no un soporte.

    Este test **no exige** que la CI pruebe 3.9: exige que la matriz de la CI y
    `requires-python` digan lo mismo. Bajar la matriz o subir el piso son las
    dos salidas válidas, y cuál es la buena la decide quien publica el paquete.
    Lo que no vale es que diverjan en silencio, que es como se llegó aquí.
    """
    ci = (RAIZ / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8")
    versiones = {
        tuple(int(x) for x in v.split("."))
        for v in re.findall(r"['\"](\d+\.\d+)['\"]", ci)
    }
    assert versiones, "la CI no declara ninguna versión de Python"
    assert min(versiones) == piso_declarado(), (
        f"la CI prueba desde {min(versiones)} y pyproject.toml promete "
        f"{piso_declarado()}. O la CI baja, o la promesa sube."
    )
