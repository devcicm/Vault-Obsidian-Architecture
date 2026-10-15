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


_CAPTURAN_IMPORT = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def _imports_con_alternativa(arbol: ast.AST) -> set[int]:
    """Los `id()` de los imports escritos dentro de un `try` cuyo `except`
    captura `ImportError`: ese módulo tiene un camino para el piso, y el que
    falte lo dice el propio código (`vault_drift_detect` declara el
    `pyproject.toml` como no leído en vez de romper). Esconder el import tras
    `importlib` lo sacaría también de la medida, pero mintiendo; escribir la
    alternativa es la salida honesta y por eso es la única que se acepta."""
    def captura(h: ast.ExceptHandler) -> bool:
        if h.type is None:
            return True
        tipos = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
        return any(isinstance(t, ast.Name) and t.id in _CAPTURAN_IMPORT for t in tipos)

    protegidos: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Try) and any(captura(h) for h in nodo.handlers):
            for sent in nodo.body:
                protegidos.update(id(n) for n in ast.walk(sent)
                                  if isinstance(n, (ast.Import, ast.ImportFrom)))
    return protegidos


def test_el_import_con_alternativa_se_acepta_y_el_desnudo_no():
    con = ast.parse("try:\n    import tomllib\nexcept ImportError:\n    tomllib = None\n")
    sin = ast.parse("import tomllib\n")
    otro = ast.parse("try:\n    import tomllib\nexcept KeyError:\n    pass\n")
    assert len(_imports_con_alternativa(con)) == 1
    assert _imports_con_alternativa(sin) == set()
    assert _imports_con_alternativa(otro) == set()


def test_ninguna_api_de_stdlib_es_posterior_al_piso():
    """Lo que no ve ningún parser: una función que no existía en 3.9.

    Alcance declarado: solo los nombres de `POSTERIORES_A_39`, y solo escritos
    literalmente. Una API alcanzada por `getattr` o por un nombre construido no
    la ve, igual que `vault_criterios` declara que no ve la copia sintáctica.
    Un import con alternativa escrita para `ImportError` no cuenta: el módulo
    sí arranca en el piso (ver `_imports_con_alternativa`).
    """
    piso = piso_declarado()
    culpables = []
    for ruta in _ficheros():
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        rel = ruta.relative_to(RAIZ).as_posix()
        protegidos = _imports_con_alternativa(arbol)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.Import, ast.ImportFrom)):
                if id(nodo) in protegidos:
                    continue
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


#: Argumento nombrado que una función de la stdlib estrenó después de 3.9:
#: (método o función, argumento) -> versión. Medido el 2026-10-15 en un
#: contenedor `python:3.9-slim` con la wheel 41.5: `vault init` moría con
#: «write_text() got an unexpected keyword argument 'newline'», y ninguno de
#: los tests de arriba lo veía, porque la función existe en 3.9 y solo el
#: argumento es nuevo. Como `POSTERIORES_A_39`, no pretende ser exhaustivo.
ARGUMENTOS_POSTERIORES_A_39 = {
    ("write_text", "newline"): "3.10",
    ("read_text", "newline"): "3.13",
    ("zip", "strict"): "3.10",
    ("dataclass", "slots"): "3.10",
    ("dataclass", "kw_only"): "3.10",
    ("glob", "case_sensitive"): "3.12",
    ("rglob", "case_sensitive"): "3.12",
}


def _nombre_llamado(llamada: ast.Call) -> str:
    f = llamada.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def test_ningun_argumento_nombrado_es_posterior_al_piso():
    """Alcance declarado: el nombre del método y el del argumento, escritos
    literalmente. No sabe de qué tipo es el objeto, así que un `write_text`
    propio con `newline=` también saldría; ninguno lo tiene hoy, y si alguno
    lo tuviera se renombra antes que abrir una excepción que esconda el caso."""
    piso = piso_declarado()
    culpables = []
    for ruta in _ficheros():
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            for kw in nodo.keywords:
                v = ARGUMENTOS_POSTERIORES_A_39.get((_nombre_llamado(nodo), kw.arg))
                if v and tuple(int(x) for x in v.split(".")) > piso:
                    culpables.append(f"{ruta.relative_to(RAIZ).as_posix()}:{nodo.lineno}: "
                                     f"{_nombre_llamado(nodo)}({kw.arg}=) (desde {v})")
    assert not culpables, (
        f"argumento que Python {piso[0]}.{piso[1]} no acepta:\n  " + "\n  ".join(sorted(culpables)))


def test_el_detector_de_argumentos_ve_el_caso_que_lo_motivo():
    llamada = ast.parse('p.write_text(t, encoding="utf-8", newline="\\n")').body[0].value
    assert _nombre_llamado(llamada) == "write_text"
    assert ("write_text", llamada.keywords[1].arg) in ARGUMENTOS_POSTERIORES_A_39


def test_la_ci_prueba_el_piso_que_se_promete():
    """Un piso que ninguna máquina ejecuta es una promesa, no un soporte.

    Este test **no exige** que la CI pruebe 3.9: exige que la matriz de la CI y
    `requires-python` digan lo mismo. Bajar la matriz o subir el piso son las
    dos salidas válidas, y cuál es la buena la decide quien publica el paquete.
    Lo que no vale es que diverjan en silencio, que es como se llegó aquí.
    """
    import yaml

    # Se lee como YAML y solo la matriz de los jobs que ejecutan la suite: un
    # regex sobre el texto contaba cualquier 'x.y', también de un job de lint o
    # de un comentario, y daba el piso por probado sin que pytest corriera en él.
    datos = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8")
    )
    versiones = {
        tuple(int(x) for x in str(v).split(".")[:2])
        for job in datos["jobs"].values()
        if any("pytest" in str(paso.get("run", "")) for paso in job.get("steps", []))
        for v in (job.get("strategy") or {}).get("matrix", {}).get("python-version", [])
    }
    assert versiones, "ningún job que ejecuta pytest declara versiones de Python"
    assert min(versiones) == piso_declarado(), (
        f"la CI prueba desde {min(versiones)} y pyproject.toml promete "
        f"{piso_declarado()}. O la CI baja, o la promesa sube."
    )
