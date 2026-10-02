"""AP-57/AP-17: el servidor MCP identifica las notas con la misma clave que Python.

`normalizeStem` del `.mjs` era una copia anterior a v40.35: no plegaba acentos
y quitaba `md` después de los puntos. Por MCP, `[[Índice]]` no encontraba
`indice.md` y `cmd.md` se confundía con `c.md`, mientras la misma consulta por
CLI respondía otra cosa. La frontera de lenguaje impide importar al dueño, así
que se contrasta ejecutando las dos sobre las mismas muestras.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from vault.kernel.normalizacion import clave_de_nombre  # noqa: E402

SERVIDOR = RAIZ / "mcp" / "nodejs" / "vault-mcp-server.mjs"
MUESTRAS = [
    "cmd", "c", "cmd.md", "NOTA.MD", "Mi Proyecto Demo", "mi-proyecto-demo.md",
    "mi_proyecto_demo", "Índice", "Über-Straße", "Łódź Øre", "v1.2", "a/b",
    "Café", "日本語 ノート", "Заметка",
]


@pytest.mark.skipif(shutil.which("node") is None, reason="sin node no hay servidor MCP que medir")
def test_ap57_el_mcp_y_python_dan_la_misma_clave():
    script = (
        f"import({json.dumps(SERVIDOR.as_uri())}).then(m => "
        f"process.stdout.write(JSON.stringify({json.dumps(MUESTRAS)}.map(m.normalizeStem))))"
    )
    salida = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    ).stdout
    del_mcp = dict(zip(MUESTRAS, json.loads(salida)))
    de_python = {m: clave_de_nombre(m) for m in MUESTRAS}
    assert del_mcp == de_python
