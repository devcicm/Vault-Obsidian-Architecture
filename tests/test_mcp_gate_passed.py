"""A-10 — un envelope con `exit_code != 0` no se lee como éxito por MCP.

Una puerta `--strict` devuelve exit 1 con un envelope completo y `ok: true`
(el informe se entregó). Quien solo mira `ok` leía «pasó». El servidor deja
`ok` como está —campo estable— y añade `passed: false` junto a `exit_code`.

Las puertas del grupo 35 no se exponen por MCP (`test_exposicion_mcp`), así que
no hay una tool expuesta que reproduzca el caso de punta a punta: lo que se
vigila es que la regla siga escrita en el único sitio que construye el envelope.
"""

import re
from pathlib import Path

FUENTE = (Path(__file__).resolve().parent.parent / "mcp" / "nodejs"
          / "vault-mcp-server.mjs").read_text(encoding="utf-8")


def test_exit_distinto_de_cero_marca_passed_false_sin_tocar_ok():
    m = re.search(r"if \(code !== 0\) \{\s*envelope\.exit_code = code;(.*?)resolve\(envelope\)",
                  FUENTE, re.S)
    assert m, "no se encuentra el bloque que adjunta exit_code"
    assert "if (envelope.ok === true) envelope.passed = false;" in m.group(1)
    assert not re.search(r"envelope\.ok\s*=(?!=)", m.group(1)), "`ok` es un campo estable"
