#!/usr/bin/env python3
"""vault_proyecto_arg — el `type=` de argparse para el `--project` de toda tool.

AP-63: el nombre de un proyecto es identidad, no texto libre. Lo que llega a la
tool ya es el slug canónico, así que lo que escribe en `project:` o en la ruta
es la identidad y no la cadena que tecleó alguien. Resolver en `type=` y no
dentro de cada tool es lo que deja medirlo: un `add_argument("--project")` sin
él es una tool que vuelve a aceptar texto libre, y `test_project_registrado`
lo nombra.

**Por qué en el núcleo.** Vivió en `vault_project` (Autoría) y cada tool de
grafo, gobernanza o ciclo de vida que lo importaba abría un cruce de contexto
nuevo. Lo leen todos los contextos, como `wrap_main`: es núcleo por forma
—fan-out de dos, fan-in de cada tool con `--project`—, no por comodidad.
`vault_project` lo reexporta.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

from vault_errors import emit_fallo
from vault_raiz import get_vault_root

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.kernel import proyectos  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402


def proyecto_registrado(tool: str) -> Callable[[str], str]:
    """`type=` de argparse que resuelve `--project` contra el registro (AP-63).

    Un nombre que no resuelve no llega a la tool: se imprime el envelope de
    `emit_fallo` con el nombre de **la tool que llama** —por eso es una
    fábrica— y se sale con 1, antes de que la tool cree nada. No se usa
    `ArgumentTypeError`: argparse lo convertiría en un texto por stderr con
    código 2, fuera del contrato de errores que leen la CLI y el MCP.

    La cadena vacía pasa tal cual: es el «sin proyecto» de las tools que lo
    declaran opcional con `default=""`, y argparse aplica `type=` también al
    default cuando es una cadena.
    """

    def _resolver(valor: str) -> str:
        if valor == "":
            return valor
        try:
            return proyectos.leer_registro(get_vault_root()).resolver(valor)
        except FalloDeDominio as fallo:
            print(json.dumps(emit_fallo(tool, fallo), ensure_ascii=False))
            raise SystemExit(1)

    _resolver.__name__ = "proyecto_registrado"
    return _resolver
