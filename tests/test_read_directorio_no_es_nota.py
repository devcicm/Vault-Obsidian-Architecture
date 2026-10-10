"""AP-51 — `vault_read` de un directorio dice que no es una nota.

Medido como consumidor el 2026-10-10: `vault_read --path 07_Knowledge`
devolvía `PERMISSION_DENIED` (en Windows, abrir un directorio para leer lanza
PermissionError). El agente lo leía como un problema de permisos del vault y
no como una ruta equivocada: la causa que da el sobre no era la que pasó.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(raiz: Path, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_read.py"), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


def test_un_directorio_no_es_una_nota_ap51(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    env = _run(raiz, "--path", "07_Knowledge")
    assert env["ok"] is False
    assert env["error_code"] == "INVALID_PATH", env
    assert "Not a note" in env["message"]
    assert env["path"] == "07_Knowledge"
