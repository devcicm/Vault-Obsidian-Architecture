"""Los índices de sección se escriben en LF, como el resto de notas.

Medido el 2026-10-05 al reindexar un vault real desde Windows: los 68
`index.md` salían en CRLF porque `vault_section_index` los escribía con
`Path.write_text`, que traduce cada `\n`. Las notas ya iban en LF por el
primitivo atómico (f8b0bb0), así que el mismo vault quedaba mezclado según
qué tool tocó cada fichero, y el `.gitattributes` del consumidor lo
renormalizaba en cada commit.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_indices_de_seccion_y_subseccion_sin_cr(tmp_path):
    env = dict(os.environ, VAULT_ROOT=str(tmp_path), VAULT_STRICT_ROOT="1",
               VAULT_AGENT="probe", PYTHONIOENCODING="utf-8")
    (tmp_path / "00_System").mkdir()
    sub = tmp_path / "07_Knowledge" / "apis"
    sub.mkdir(parents=True)
    nota = "---\ntitle: JWT\ntype: concept\n---\n\n# JWT\n\nToken firmado.\n"
    (tmp_path / "07_Knowledge" / "jwt.md").write_bytes(nota.encode("utf-8"))
    (sub / "rest.md").write_bytes(nota.replace("JWT", "REST").encode("utf-8"))
    subprocess.run([sys.executable, str(SCRIPTS / "vault_section_index.py"),
                    "--folder", "07_Knowledge"],
                   capture_output=True, env=env, timeout=300, check=True)
    escritos = [tmp_path / "07_Knowledge" / "index.md", sub / "index.md"]
    escritos += [p for p in (tmp_path / "00_System").glob("vault-*.md")]
    for indice in escritos:
        assert indice.exists(), indice
        assert b"\r" not in indice.read_bytes(), indice.name
