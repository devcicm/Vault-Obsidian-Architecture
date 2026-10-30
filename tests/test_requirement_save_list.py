"""D-05 -- `vault_requirement_save --list` enumera los requisitos sin escribir."""
import json
import os
import subprocess
import sys
from pathlib import Path

from vault_base import copiar_vault

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vault_requirement_save.py"


def _run(raiz, *argv):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPT), *argv], env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(raiz.parent), timeout=300)
    return p.returncode, json.loads(p.stdout[p.stdout.index("{"):])


def test_list_enumera_y_no_escribe(tmp_path):
    raiz = copiar_vault(tmp_path / "vault", "demo")
    rc, r = _run(raiz, "--list")
    assert rc == 0 and r["ok"] is True and r["count"] == 0
    rc, g = _run(raiz, "--project", "demo", "--title", "Login seguro",
                 "--type", "functional", "--priority", "must-have",
                 "--description", "El sistema exige autenticacion antes de operar.")
    assert rc == 0 and g["ok"] is True, g
    antes = sorted(p.name for p in raiz.rglob("*") if p.is_file())
    rc, r = _run(raiz, "--list", "--project", "demo")
    assert rc == 0 and r["count"] == 1 and r["requirements"][0]["title"] == "Login seguro"
    assert sorted(p.name for p in raiz.rglob("*") if p.is_file()) == antes
    assert _run(raiz, "--list", "--project", "otro")[1]["ok"] is False  # slug no registrado
