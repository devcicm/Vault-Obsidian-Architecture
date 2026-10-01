"""`vault_search` sin índice nombra la tool que lo regenera, no un script.

Medido en v40.34 con la wheel: el mensaje decía «Run vault_index.py first»,
pero `vault_index` no está en el catálogo —ni la CLI ni el MCP la ofrecen— y el
`recovery.tool` del mismo envelope ya era `vault_reindex`. Mensaje y
recuperación se contradecían dentro del mismo JSON.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_sin_indice_el_mensaje_y_la_recuperacion_nombran_la_misma_tool(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "99_Index").mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    proceso = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_search.py"), "--query", "algo"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=120,
    )
    salida = proceso.stdout.strip()
    r = json.loads(salida[salida.index("{"):])

    assert r["error_code"] == "INDEX_NOT_FOUND", r
    assert "vault_index.py" not in r["message"], r["message"]
    assert r["recovery"]["tool"] in r["message"], r
