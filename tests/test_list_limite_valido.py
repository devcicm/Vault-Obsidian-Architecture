"""AP-51 — `vault_list --limit` fuera de rango es un error, no un listado.

Medido como consumidor el 2026-10-10: `--limit 0` devolvía `ok: true` con una
nota (el corte se comprobaba después de añadirla) y `--limit -3` lo mismo. Un
agente que pide cero recibía uno y no tenía forma de saber que el límite se
había ignorado. Un límite que no es positivo no admite lectura legítima.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(raiz: Path, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_list.py"), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "07_Knowledge").mkdir(parents=True)
    for n in ("a", "b"):
        (r / "07_Knowledge" / f"{n}.md").write_text(
            f"---\ntitle: {n}\nstatus: draft\n---\n# {n}\n", encoding="utf-8")
    return r


@pytest.mark.parametrize("limite", ["0", "-3"])
def test_un_limite_no_positivo_se_rechaza(raiz, limite):
    env = _run(raiz, "--folder", "07_Knowledge", "--limit", limite)
    assert env["ok"] is False and env["error_code"] == "INVALID_INPUT", env
    assert "notes" not in env


def test_un_limite_positivo_corta(raiz):
    env = _run(raiz, "--folder", "07_Knowledge", "--limit", "1")
    assert env["ok"] is True and env["total"] == 1
