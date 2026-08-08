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
import json
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

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


def _hash_normalizado(nodo: ast.AST) -> str:
    """Hash del nodo tal y como el intérprete lo ve, no como está escrito.

    `ast.unparse` es lo que hace estable la firma: reconstruye el código desde
    el árbol, así que comentarios, comillas, saltos de línea y sangrado ya no
    existen cuando se hashea. Si `unparse` no puede con el nodo —no debería,
    pero no se adivina— se cae a su volcado estructural, que es igual de
    determinista aunque más largo.
    """
    try:
        texto = ast.unparse(nodo)
    except Exception:
        texto = ast.dump(nodo, annotate_fields=True, include_attributes=False)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:8]


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
    v1 = datos_previos.get("sites_v1_superseded") or [
        s for s in datos_previos.get("sites", []) if isinstance(s, str)
    ]
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
    path.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(sitios)
