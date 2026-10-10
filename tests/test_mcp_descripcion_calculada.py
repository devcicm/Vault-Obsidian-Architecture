"""Un `help=` calculado llega al esquema MCP con el texto que enseña argparse.

Medido el 2026-10-08: de los `help=` de las tools del catálogo, 42 no eran una
cadena literal —41 f-strings como `f"Tope de nodos (default: {DEFAULT_MAX_NODES})"`
y una concatenación— y el extractor solo leía `ast.Constant`, así que salían
al esquema con `description: ""`. Justo los que llevan el default o el
vocabulario derivado del registro, que es lo que un agente necesita para
rellenar el argumento sin probar a ciegas.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402

PUBLICADO = json.loads(
    (ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8")
)["tools"]

import vault_grafo_import as gi  # noqa: E402


def _sitios_con_help_calculado():
    for nombre, tool in sorted(TOOLS_CATALOG.items()):
        script = tool.get("script")
        if nombre not in PUBLICADO or not script or not (SCRIPTS / script).is_file():
            continue
        arbol = ast.parse(gi.codigo_de(SCRIPTS / script).read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
                continue
            largos = [a.value for a in nodo.args
                      if isinstance(a, ast.Constant) and str(a.value).startswith("--")]
            ayuda = next((k.value for k in nodo.keywords if k.arg == "help"), None)
            if largos and ayuda is not None and not isinstance(ayuda, ast.Constant):
                param = largos[0][2:]
                if param in PUBLICADO[nombre]["inputSchema"]["properties"]:
                    yield nombre, script, param


SITIOS = list(_sitios_con_help_calculado())


def test_hay_help_calculados_que_medir():
    # Sin esto el test de abajo pasaría vacío si el recorrido dejara de verlos.
    assert len(SITIOS) >= 20, len(SITIOS)


def _sin_blancos(texto: str) -> str:
    # argparse reparte la ayuda en líneas y puede cortar por un guion.
    return re.sub(r"\s+", "", texto)


@pytest.mark.parametrize("nombre,script,param", SITIOS)
def test_la_descripcion_es_la_ayuda_de_la_cli(nombre, script, param):
    """Criterio del consumidor (AP-44): no la expresión evaluada por el
    catálogo, sino el texto que la propia CLI imprime con `--help`."""
    descripcion = PUBLICADO[nombre]["inputSchema"]["properties"][param].get("description", "")
    assert descripcion, (nombre, param)
    declarada = (TOOLS_CATALOG[nombre].get("params", {}).get(param) or {}).get("description")
    if declarada:
        return  # la escrita a mano gana a propósito (reconciled_params)
    assert _sin_blancos(descripcion) in _sin_blancos(_ayuda_de_la_cli(script)), (
        nombre, param, descripcion)


def _ayuda_de_la_cli(script: str) -> str:
    """El `--help` del script y, si tiene subcomandos, el de cada uno: la
    ayuda de `vault_token_counter serve --port` solo sale en el segundo."""
    def _help(*args):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *args, "--help"],
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=120).stdout

    raiz = _help()
    m = re.search(r"^usage:[^{]*\{([\w,-]+)\}", raiz, re.MULTILINE)
    subcomandos = m.group(1).split(",") if m else []
    return raiz + "".join(_help(sub) for sub in subcomandos)
