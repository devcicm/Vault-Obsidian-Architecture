"""La pista de un `vault run` rechazado dice qué hacer con la CLI instalada.

Medido en v40.34 con la wheel: `vault run vault_gate` y `vault run nombre_inventado`
respondían `INVALID_ACTION` con la pista genérica del catálogo, «Ejecutar el
script con --help para ver las acciones disponibles». Quien usa la instalación
no tiene script que ejecutar, y la pista no distinguía una tool que no existe
de una que existe pero es mantenimiento del estándar.
"""

import json

from vault import product_cli
from vault.meta_toolkit.catalogo_producto import catalogo_producto


def _pista(capsys, argv):
    product_cli.main(argv)
    return json.loads(capsys.readouterr().err)["recovery"]["hint"]


def test_una_tool_desconocida_remite_a_tools_list(capsys):
    pista = _pista(capsys, ["run", "vault_que_no_existe"])
    assert "--help" not in pista
    assert "vault tools list" in pista


def test_una_tool_de_mantenimiento_dice_donde_se_ejecuta(capsys):
    mantenimiento = sorted(n for n, t in catalogo_producto().items() if t.clase != "runtime")
    assert mantenimiento, "el catálogo ya no declara tools de mantenimiento"
    pista = _pista(capsys, ["run", mantenimiento[0]])
    assert "--help" not in pista
    assert "checkout" in pista
