"""AP-47 — la recuperación de AUTO_INDEX_ERROR rehace lo que quedó atrás.

Medido el 2026-10-07 al revisar qué pistas del catálogo puede seguir el perfil
`agente`: AUTO_INDEX_ERROR se emite en dos sitios de `vault_io` tras una
escritura que sí ocurrió —el índice de sección (`_auto_section_index`) y el
grafo (`_auto_grafo`)—, pero su recuperación era `run_tool` sin `tool`, con una
pista que mandaba a `vault_section_index`. Esa tool no está en el perfil y no
toca el grafo, así que para el segundo sitio no recuperaba nada.
`vault_reindex --graph` rehace las dos cosas (e1f4982).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import ERROR_CATALOG  # noqa: E402


def _tool(raiz: Path, script: str, *argv: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=300)
    salida = p.stdout.strip()
    assert salida, p.stderr[-1000:]
    return json.loads(salida[salida.index("{"):])


def test_ap47_seguir_la_recuperacion_rehace_indice_de_seccion_y_grafo(tmp_path):
    rec = ERROR_CATALOG["AUTO_INDEX_ERROR"]["recovery"]
    assert rec["action"] == "run_tool" and rec.get("tool"), rec

    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _tool(raiz, "vault_init")["ok"] is True
    indice = raiz / "21_QA" / "index.md"
    grafo = raiz / "99_Index" / "graph.json"
    for derivado in (indice, grafo):
        if derivado.exists():
            derivado.unlink()

    assert _tool(raiz, rec["tool"], *rec.get("args", []))["ok"] is True
    assert indice.exists(), "el índice de sección sigue sin rehacer"
    assert grafo.exists(), "el grafo sigue sin rehacer"
