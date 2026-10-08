"""Ningún parámetro del esquema MCP se publica sin descripción.

Medido el 2026-10-08: 107 de los parámetros de `tools-catalog.json` salían con
`description: ""`. 21 eran ayudas calculadas que el extractor no leía; los
otros 86, de 13 tools, no tenían `help=` en la CLI ni descripción en el
catálogo. Para un agente, el nombre del parámetro era todo el contrato: no
sabía que `--services` es un array JSON, que `--env_vars` lleva nombres y no
valores, ni que `--rto` vacío toma el objetivo de la severidad.

La ayuda se escribe donde la lee también quien usa la CLI —el `help=` del
script— y llega al esquema por el extractor; la descripción a mano del
catálogo sigue ganando cuando existe.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLICADOS = [
    ROOT / "mcp" / "nodejs" / "tools-catalog.json",
    ROOT / "vault" / "meta_toolkit" / "tools-catalog.json",
]


def _sin_descripcion(ruta: Path):
    tools = json.loads(ruta.read_text(encoding="utf-8"))["tools"]
    return sorted(
        (nombre, param)
        for nombre, tool in tools.items()
        for param, prop in tool["inputSchema"]["properties"].items()
        if not str(prop.get("description", "")).strip()
    )


def test_todo_param_publicado_tiene_descripcion():
    for ruta in PUBLICADOS:
        assert _sin_descripcion(ruta) == [], ruta.relative_to(ROOT).as_posix()


def test_el_recorrido_ve_los_params():
    # Sin esto el test de arriba pasaría vacío si cambiara la forma del JSON.
    tools = json.loads(PUBLICADOS[0].read_text(encoding="utf-8"))["tools"]
    assert sum(len(t["inputSchema"]["properties"]) for t in tools.values()) > 500
