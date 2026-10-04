"""`vault_move --json` responde con un envelope también cuando el uso es inválido.

Medido en la QA de producto (2026-10-04): el MCP invoca `vault_move` siempre con
`--json`, y `--impact` sin `--to` o `--folder` sin `--to-folder` imprimían
«Error: …» en texto plano. El servidor recibía algo que no era un envelope.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vault_move.py"


def _mover(raiz, *args):
    (raiz / "99_Index").mkdir(exist_ok=True)
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env,
                          timeout=120)


@pytest.mark.parametrize("args", [
    ("--impact", "--from", "07_Knowledge/a.md", "--dry-run"),
    ("--folder", "07_Knowledge"),
    (),
])
def test_uso_invalido_con_json_es_un_envelope(tmp_path, args):
    p = _mover(tmp_path, *args, "--json")
    assert p.returncode == 1
    sobre = json.loads(p.stdout)
    assert sobre["ok"] is False
    assert sobre["error_code"] == "INVALID_INPUT"
    assert sobre["tool"] == "vault_move"


def test_sin_json_el_mensaje_sigue_siendo_para_humanos(tmp_path):
    p = _mover(tmp_path, "--impact", "--from", "07_Knowledge/a.md")
    assert p.returncode == 1
    assert p.stdout.strip() == "Error: --impact requiere --from y --to"
