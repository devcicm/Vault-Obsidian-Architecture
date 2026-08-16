#!/usr/bin/env python3
"""vault_subproceso — cómo se lee la salida de un proceso hijo. Nada más.

Módulo hoja: **no importa ningún `vault_*`**. Si algún día lo necesita, ha
dejado de ser un recurso y pierde el sitio aquí (AP-62).

## Por qué existe (v40.30)

`subprocess.run(..., text=True)` sin `encoding` decodifica con
`locale.getpreferredencoding()`, que es la del **sistema donde corre**, no la
del proceso que escribió. Todo este toolkit emite UTF-8 —lo fija
`PYTHONIOENCODING`, y los envelopes van con `ensure_ascii=False`—, así que el
padre leía con un criterio distinto del que usó el hijo para escribir. Es el
mismo defecto que persigue AP-44, cruzando una frontera de proceso en vez de
una de módulo: el productor y el consumidor midieron el mismo dato con varas
distintas.

Medido al instalar el toolkit fuera del repo y correr `vault_init`, el resultado
son acentos rotos **dentro de los envelopes anidados** que la tool devuelve:

    "el Ã­ndice dejÃ³ de reflejar el disco"   en vez de   "el índice dejó..."

Y no se queda en lo cosmético. En Windows con cp1252 el texto se corrompe en
silencio y se escribe corrompido al vault; en una locale sin equivalencias
—cp932, cp949— `subprocess` levanta `UnicodeDecodeError` y la tool entera cae
por un acento. Eso convierte «funciona en mi máquina» en la definición literal
del problema: los 23 sitios pasaban en verde aquí y solo aquí.

## Por qué un dueño y no 23 `encoding="utf-8"`

Porque añadir el argumento en 23 llamadas es escribir el mismo criterio 23
veces, que es AP-57 con nombre y apellidos — y cometerlo en el repo que publica
esa norma. El criterio «la salida de un hijo se lee como UTF-8» vive aquí, y
quien lance un proceso entra por esta puerta.

`errors="replace"` es deliberado: un byte suelto no debe tumbar una tool que
solo quería leer un JSON. Se degrada el carácter, no la ejecución.
"""

from __future__ import annotations

import subprocess
from typing import Any

#: Cómo se decodifica todo hijo de este toolkit. Un solo sitio.
CODIFICACION = "utf-8"

#: Qué hacer con un byte que no encaja. Ver el docstring: degradar el carácter
#: es preferible a tumbar la tool, porque el llamador casi siempre está detrás
#: de un `json.loads` que sí sabrá quejarse si el contenido no sirve.
ERRORES = "replace"


def ejecutar(cmd: list[str], **kwargs: Any) -> "subprocess.CompletedProcess[str]":
    """`subprocess.run` que lee al hijo con el criterio con que el hijo escribe.

    Fija `text`, `encoding` y `errors`; lo demás pasa tal cual, así que
    `capture_output`, `cwd`, `timeout` o `env` se usan igual que siempre.

    Un llamador puede sobreescribir `encoding` —hace falta para hablar con un
    proceso ajeno que no sea UTF-8— y por eso no se impone con `dict` fijo: la
    norma cubre a los hijos de este toolkit, no a cualquier binario del mundo.
    Lo que ya no se puede es **olvidarlo**, que era el caso real.
    """
    kwargs.setdefault("encoding", CODIFICACION)
    kwargs.setdefault("errors", ERRORES)
    kwargs.pop("text", None)
    kwargs.pop("universal_newlines", None)
    return subprocess.run(cmd, **kwargs)


def sitios_sin_codificacion(raices: "list[str] | None" = None) -> list[str]:
    """Llamadas a `subprocess` que decodifican con la locale de la máquina.

    Es el guard de esta norma y vive junto al dueño a propósito: un detector que
    viviera en otro módulo tendría que reescribir qué cuenta como violación, que
    es la copia de criterio que este fichero existe para evitar.

    Detecta por AST y no por texto: `text=True` puede estar en cualquier orden
    entre los argumentos, y un grep por `encoding` daría por bueno el fichero
    que lo usa en otra llamada distinta.

    Lo que **no** ve: un `subprocess.run` construido dinámicamente, y un binario
    de otro lenguaje que lance procesos por su cuenta. El alcance se declara en
    vez de suponerse, que es la regla de la casa.
    """
    import ast
    import pathlib

    hallazgos: list[str] = []
    for base in (raices or ["scripts", "cli", "vault", "tests"]):
        for ruta in sorted(pathlib.Path(base).rglob("*.py")):
            if ruta.name == pathlib.Path(__file__).name:
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Call):
                    continue
                if ast.unparse(nodo.func) not in (
                    "subprocess.run", "subprocess.Popen", "subprocess.check_output",
                ):
                    continue
                claves = {k.arg for k in nodo.keywords}
                pide_texto = "text" in claves or "universal_newlines" in claves
                if pide_texto and "encoding" not in claves:
                    hallazgos.append(f"{ruta.as_posix()}:{nodo.lineno}")
    return sorted(hallazgos)
