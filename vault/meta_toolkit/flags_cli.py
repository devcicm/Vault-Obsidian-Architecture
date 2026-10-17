"""Hoja canónica: qué argumentos declara un script, leídos de sus `add_argument`.

Hasta v41.8 había cinco lectores del mismo dato y no decían lo mismo: el AST
de `vault_mcp_catalog.argparse_params` y cuatro regex —`vault_spec_validate`,
`vault_manifest`, `vault_spec_memory` y `vault_doc_sync`—. El productor de
`tool-spec.json` (`vault_manifest`) y su validador (`vault_spec_validate`)
leían cada uno con el suyo, que es AP-44 —el que mide se certifica con su
propio criterio— cometido por AP-57: un criterio con dueño reescrito en cuatro
sitios. Las regex solo veían el primer nombre de la llamada (`"-o", "--output"`
dejaba fuera `--output`), contaban `required=True` en el texto de un `help=` y
encontraban `add_argument(` dentro de una cadena.

Estático a propósito: importar un script para preguntarle su parser lo
ejecuta, y varios escriben en el vault al importarse o al construirlo. Lo que
este módulo no hace es **evaluar**: un `choices=` o un `help=` que no son
literales los evalúa `vault_mcp_catalog` en el módulo que se los da a
argparse; aquí se devuelve el nodo tal cual.

Sin dependencias fuera de `ast`: lo importan cinco módulos del contexto
`meta_toolkit` y ninguno debe arrastrar a otro para leer un parser.
"""

import ast
from typing import Any, Dict, List, Optional, Set


class Declaracion:
    """Una llamada `add_argument` y lo que se puede leer de ella sin evaluarla."""

    __slots__ = ("nombres", "kw", "receptor", "linea")

    def __init__(self, nombres: List[str], kw: Dict[str, ast.AST], receptor: Optional[str],
                 linea: int = 0):
        #: Los nombres literales de la llamada, en orden: `["-o", "--output"]`.
        self.nombres = nombres
        #: Los argumentos con nombre, como nodos del AST.
        self.kw = kw
        #: El nombre de la variable sobre la que se llama (`parser`, `grupo`…).
        self.receptor = receptor
        self.linea = linea

    @property
    def largo(self) -> Optional[str]:
        """El primer `--flag` de la llamada: el nombre con el que se publica."""
        return next((n for n in self.nombres if n.startswith("--")), None)

    @property
    def posicional(self) -> bool:
        return bool(self.nombres) and not self.nombres[0].startswith("-")

    def constante(self, clave: str) -> Any:
        valor = self.kw.get(clave)
        return valor.value if isinstance(valor, ast.Constant) else None

    @property
    def accion(self) -> Optional[str]:
        """`action=` como texto; `BooleanOptionalAction` se nombra `negable`.

        Hasta v41.8 `argparse_params` solo leía `action` literal, así que
        `action=argparse.BooleanOptionalAction` salía sin acción y el flag se
        publicaba como texto.
        """
        valor = self.kw.get("action")
        if isinstance(valor, ast.Constant):
            return valor.value
        if valor is not None and ast.unparse(valor).split(".")[-1] == "BooleanOptionalAction":
            return "negable"
        return None

    @property
    def obligatorio(self) -> bool:
        return self.constante("required") is True


def declaraciones(fuente: str) -> List[Declaracion]:
    """Todas las llamadas `add_argument` del módulo, en orden de aparición.

    Un `SyntaxError` se deja escapar: un script que no se parsea tampoco se
    ejecuta, y devolver una lista vacía lo haría pasar por un script sin flags.
    """
    salida: List[Declaracion] = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
            continue
        nombres = [a.value for a in nodo.args
                   if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not nombres:
            continue
        receptor = nodo.func.value.id if isinstance(nodo.func.value, ast.Name) else None
        salida.append(Declaracion(nombres, {k.arg: k.value for k in nodo.keywords if k.arg},
                                  receptor, nodo.lineno))
    # ast.walk recorre en anchura: el orden de aparición lo da la línea.
    salida.sort(key=lambda d: d.linea)
    return salida


def flags_aceptados(fuente: str) -> Set[str]:
    """Todo nombre con guion que la CLI acepta, cortos incluidos.

    Un flag `negable` acepta también su `--no-<flag>`: es lo que argparse
    genera y lo que un ejemplo documentado puede usar.
    """
    aceptados: Set[str] = set()
    for d in declaraciones(fuente):
        guiones = [n for n in d.nombres if n.startswith("-")]
        aceptados.update(guiones)
        if d.accion == "negable":
            aceptados.update("--no-" + n[2:] for n in guiones if n.startswith("--"))
    return aceptados


def obligatorios(fuente: str) -> List[str]:
    """Los flags con `required=True`, por su nombre largo si lo tienen."""
    salida: List[str] = []
    for d in declaraciones(fuente):
        if d.posicional or not d.obligatorio:
            continue
        nombre = d.largo or d.nombres[0]
        if nombre not in salida:
            salida.append(nombre)
    return salida
