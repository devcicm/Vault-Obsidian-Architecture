#!/usr/bin/env python3
"""Firma estable de un sitio de código, para baselines que no mienten al moverse.

Las baselines de AP-37, AP-51 y AP-52 se indexaban por `módulo:línea`. Ese
índice tiene un defecto que no es teórico: **insertar diez líneas de comentario
encima de un sitio conocido lo reporta como nuevo y al viejo como resuelto**,
sin que la deuda haya cambiado en nada. Pasó tres veces en una sola semana, y
las tres se resolvieron verificando a mano tres condiciones —`offenders_total`
igual a `baseline_size`, tantos nuevos como resueltos, todos en el módulo que se
tocó— antes de recongelar.

Un guard cuya corrección depende de que una persona ejecute bien una receta de
tres pasos no es un guard: es una convención con un JSON al lado. Y su forma
legítima y su forma catastrófica se teclean igual (`--freeze`), que es la peor
propiedad que puede tener una operación.

La firma sustituye la línea por tres cosas que sí describen el sitio:

    vault_audit.py::_detect_broken_links::a3f9c1e2
    └ módulo        └ función contenedora   └ hash del código normalizado

El hash sale de `ast.unparse`, no del texto: comentarios, saltos de línea y
espaciado desaparecen antes de hashear. Mover el sitio, renombrar una variable
de otra función o reindentar el fichero **no** cambian la firma. Cambiar el
cuerpo del handler sí, y debe: si el código que se tragaba el fallo ya no es el
mismo código, la deuda que se congeló tampoco es la misma.

## Lo que la firma sigue sin distinguir, dicho en voz alta

Dos sitios idénticos dentro de la misma función colisionan — mismo módulo,
mismo qualname, mismo cuerpo. Se desempatan con un ordinal por orden de
aparición (`…::a3f9c1e2#2`). Es estable mientras no se reordenen entre sí, y
reordenar dos handlers idénticos no cambia la deuda. Declararlo aquí es más
barato que descubrirlo dentro de un `--freeze`.
"""

import ast
import hashlib
import io
import json
import re
import tokenize
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import vault_baseline

#: Versión del formato de baseline que consume este módulo. La v1 —lista plana
#: de `módulo:línea`— no se borra: se conserva en la propia baseline bajo
#: `sites_v1_superseded`, con el motivo escrito (no-derogación).
SCHEMA = 2


def mapa_de_qualnames(arbol: ast.AST) -> Dict[int, str]:
    """`id(nodo) -> nombre cualificado de la función/clase que lo contiene`.

    Se calcula una vez por módulo. `ast` no guarda el padre de cada nodo, y
    recalcularlo por sitio convertiría el audit en cuadrático sobre 118 ficheros.
    """
    mapa: Dict[int, str] = {id(arbol): ""}

    def recorrer(nodo: ast.AST, prefijo: str) -> None:
        for hijo in ast.iter_child_nodes(nodo):
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                propio = f"{prefijo}.{hijo.name}" if prefijo else hijo.name
                mapa[id(hijo)] = propio
                recorrer(hijo, propio)
            else:
                mapa[id(hijo)] = prefijo
                recorrer(hijo, prefijo)

    recorrer(arbol, "")
    return mapa


#: `ast.unparse` no es igual en todas las versiones, y una baseline que solo
#: vale en el intérprete que la congeló es una baseline que falla el día que la
#: CI corre otra — que es exactamente lo que pasó el 2026-11-02: la baseline se
#: congeló en 3.14 y la CI (3.9–3.12) reportó dos sitios "nuevos" sin que una
#: sola línea se hubiera movido.
#:
#: La diferencia medida es una: 3.9–3.11 escriben paréntesis en el DESTINO de
#: un desempaquetado de tupla y 3.12+ no.
#:
#:     3.9    (salida, error) = p.communicate()
#:     3.14   salida, error = p.communicate()
#:     3.9    for (linea, bloque) in _todos_los_bloques():
#:     3.14   for linea, bloque in _todos_los_bloques():
#:
#: Se normaliza a la forma SIN paréntesis, que es la de 3.12+. Solo en las dos
#: posiciones donde unparse los pone —destino de una asignación y destino de un
#: `for`, que incluye las comprensiones—: quitarlos en cualquier otro sitio
#: cambiaría el sentido de una tupla pasada como argumento (`f((a, b))` no es
#: `f(a, b)`).
_PARENTESIS_DE_DESTINO = (
    (re.compile(r"^(\s*)\((\w+(?:\s*,\s*\w+)+)\)(\s*=\s*)", re.MULTILINE), r"\1\2\3"),
    (re.compile(r"(\bfor\s+)\((\w+(?:\s*,\s*\w+)+)\)(\s+in\s+)"), r"\1\2\3"),
)


def _re_comillar_fstrings(texto: str) -> str:
    """Pone comilla doble al f-string que 3.12 escribe con simple por dentro.

    PEP 701 cambió el tokenizado: desde 3.12 un f-string es
    `FSTRING_START ... FSTRING_END`, y con él cambió lo que `unparse` emite
    cuando el f-string lleva comillas dentro:

        3.12   f'{recuperacion['tool']}.py'      ← comilla simple fuera
        3.14   f"{recuperacion['tool']}.py"      ← comilla doble fuera

    La regla es **simétrica**: solo se toca el f-string cuyo delimitador es `'`
    y que lleva un `'` dentro (y ningún `"`). En 3.14 ese caso ya viene con
    comilla doble y en 3.9–3.11 el tokenizador no expone los f-strings, así
    que en las dos es un **no-op** — la baseline congelada sigue valiendo y
    este arreglo no obliga a migrarla.
    """
    if not hasattr(tokenize, "FSTRING_START"):
        # 3.9–3.11: sus f-strings no llegan como tokens y su `unparse` ya
        # coincide con el de 3.14 (lo normaliza el paréntesis de destino).
        return texto
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(texto).readline))
    except (tokenize.TokenError, IndentationError):
        return texto

    cambios = []
    abiertos = []  # [(indice_del_token, lleva_simple, lleva_doble)]
    for i, tok in enumerate(tokens):
        if tok.type == tokenize.FSTRING_START:
            abiertos.append([i, False, False])
            continue
        if not abiertos:
            continue
        if tok.type == tokenize.FSTRING_END:
            inicio, con_simple, con_doble = abiertos.pop()
            arranque = tokens[inicio]
            s = arranque.string
            if not (s and s[0] in "fF"):
                continue
            # El delimitador que aparece DENTRO obliga a cambiar al otro: es
            # lo que hace 3.14 y lo que 3.12 no hace. Si aparecen las dos, no
            # se toca: cambiar cambiaría el sentido del texto.
            if s.endswith("'") and con_simple and not con_doble and tok.string == "'":
                cambios.append((arranque.start, arranque.end, s[0] + '"'))
                cambios.append((tok.start, tok.end, '"'))
            elif s.endswith('"') and con_doble and not con_simple and tok.string == '"':
                cambios.append((arranque.start, arranque.end, s[0] + "'"))
                cambios.append((tok.start, tok.end, "'"))
            continue
        if tok.type == tokenize.STRING:
            if "'" in tok.string:
                abiertos[-1][1] = True
            if '"' in tok.string:
                abiertos[-1][2] = True

    if not cambios:
        return texto
    lineas = texto.splitlines(keepends=True)
    inicios = [0]
    for linea in lineas:
        inicios.append(inicios[-1] + len(linea))

    def absoluta(pos):
        fila, columna = pos
        return inicios[fila - 1] + columna

    trozos = []
    cursor = 0
    for inicio, fin, nuevo in sorted(cambios):
        a, b = absoluta(inicio), absoluta(fin)
        trozos.append(texto[cursor:a])
        trozos.append(nuevo)
        cursor = b
    trozos.append(texto[cursor:])
    return "".join(trozos)


def _texto_canonico(nodo: ast.AST) -> str:
    """El código del nodo, normalizado para no depender del intérprete."""
    try:
        texto = ast.unparse(nodo)
    except Exception:
        texto = ast.dump(nodo, annotate_fields=True, include_attributes=False)
    texto = _re_comillar_fstrings(texto)
    for patron, reemplazo in _PARENTESIS_DE_DESTINO:
        texto = patron.sub(reemplazo, texto)
    return texto


def _hash_normalizado(nodo: ast.AST) -> str:
    """Hash del nodo tal y como el intérprete lo ve, no como está escrito.

    `ast.unparse` es lo que hace estable la firma: reconstruye el código desde
    el árbol, así que comentarios, comillas, saltos de línea y sangrado ya no
    existen cuando se hashea. Si `unparse` no puede con el nodo —no debería,
    pero no se adivina— se cae a su volcado estructural, que es igual de
    determinista aunque más largo.

    Y lo que `unparse` sí cambia entre versiones se normaliza antes de hashear
    (`_texto_canonico`): una firma que solo vale en un intérprete no sirve para
    una baseline versionada que corre en seis.
    """
    return hashlib.sha1(_texto_canonico(nodo).encode("utf-8")).hexdigest()[:8]


def firmar(modulo: str, qualname: str, nodo: ast.AST) -> str:
    """Firma de un sitio, sin desempatar. Usa `firmar_todos` para una lista."""
    return f"{modulo}::{qualname or '<module>'}::{_hash_normalizado(nodo)}"


def firmar_todos(sitios: Iterable[Tuple[str, str, ast.AST]]) -> List[str]:
    """Firma una secuencia ya ordenada, añadiendo el ordinal a las colisiones.

    El orden de entrada es el de aparición en el fichero. Dos sitios idénticos
    en la misma función reciben `#2`, `#3`… — ver el aviso del docstring del
    módulo sobre qué garantiza y qué no ese desempate.
    """
    vistas: Dict[str, int] = {}
    salida: List[str] = []
    for modulo, qualname, nodo in sitios:
        base = firmar(modulo, qualname, nodo)
        vistas[base] = vistas.get(base, 0) + 1
        salida.append(base if vistas[base] == 1 else f"{base}#{vistas[base]}")
    return salida


# ────────────────────────────────────────────────────────────────────────────
# Baseline v2 — el fichero, compartido por los audits que lo usan
# ────────────────────────────────────────────────────────────────────────────
# Vive aquí y no copiado en cada audit por lo mismo que AP-05: dos lectores del
# mismo formato acaban discrepando en el caso raro, y el caso raro de una
# baseline es justo el que decide si se congela deuda nueva.


def cargar_baseline(path: Path) -> Tuple[Set[str], int, Dict]:
    """Devuelve `(firmas, esquema, datos_crudos)`.

    Una baseline v1 se lee sin firmas y con esquema 1: quien la reciba así debe
    exigir `--migrate` en vez de tratarla como vacía. Devolver un conjunto
    vacío y seguir sería estrenar la deuda entera como "nueva" — o peor, como
    "resuelta" — que es el fallo que este módulo existe para eliminar.
    """
    if not path.exists():
        return set(), SCHEMA, {}
    datos = json.loads(path.read_text(encoding="utf-8"))
    esquema = int(datos.get("schema", 1))
    if esquema < SCHEMA:
        return set(), esquema, datos
    firmas = {s["firma"] for s in datos.get("sites", []) if isinstance(s, dict)}
    return firmas, esquema, datos


def escribir_baseline(
    path: Path, norma: str, descripcion: str,
    sitios: List[Dict], datos_previos: Dict,
) -> int:
    """Escribe la baseline v2 conservando la lista v1 que sustituye.

    `sites_v1_superseded` no es nostalgia: es la única forma de auditar después
    si la migración perdió o inventó un sitio. Se anota, no se borra.
    """
    salida = {
        "norm": norma,
        "schema": SCHEMA,
        "description": descripcion,
        "sites": sorted(sitios, key=lambda s: s["firma"]),
    }
    # El segundo `--freeze` es el que destruía la anotación. En la primera
    # llamada `sites_v1_superseded` no existe y `v1` sale de los strings de la
    # baseline v1; en la segunda ya es el **dict** anotado, y `sorted(v1)`
    # devolvía sus cuatro claves —`reason`, `since`, `sites`, `superseded_by`—
    # como si fueran los 86 sitios migrados. La no-derogación aguantaba una
    # llamada y se perdía en la siguiente, en silencio y dentro del código
    # escrito para conservarla.
    previo = datos_previos.get("sites_v1_superseded")
    if isinstance(previo, dict):
        v1 = [s for s in previo.get("sites", []) if isinstance(s, str)]
    elif isinstance(previo, list):
        v1 = [s for s in previo if isinstance(s, str)]
    else:
        v1 = [s for s in datos_previos.get("sites", []) if isinstance(s, str)]
    if v1:
        salida["sites_v1_superseded"] = {
            "superseded_by": "sites[].firma",
            "since": "v40.6",
            "reason": (
                "Indexar por `módulo:línea` reportaba como deuda nueva cualquier "
                "sitio desplazado por una inserción de líneas. Se conserva para "
                "poder auditar la migración."
            ),
            "sites": sorted(v1),
        }
    # El fichero lo escribe su dueño (AP-57), que además conserva las claves
    # que este módulo no conoce, como `objetivo`.
    vault_baseline.escribir(
        path, "sites", norma, descripcion, salida.pop("sites"),
        extra={k: v for k, v in salida.items() if k != "description"},
    )
    return len(sitios)
