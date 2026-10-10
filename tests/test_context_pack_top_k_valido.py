"""AP-51 — `vault_context_pack` rechaza un `--top-k` o `--excerpt-tokens` no positivo.

Medido como consumidor el 2026-10-10: `--top-k 0` devolvía `ok: true` con un
paquete vacío, indistinguible de «no hay nada relevante», y un negativo cortaba
`candidates[:-1]`, es decir, todas menos la última. `--budget` ya se rechazaba
con INVALID_BUDGET; los otros dos topes numéricos no.
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
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_context_pack.py"), *args],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=300,
    )
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "07_Knowledge").mkdir(parents=True)
    (r / "07_Knowledge" / "replicacion.md").write_text(
        "---\ntitle: Replicación de la base\nstatus: draft\ntype: knowledge\n"
        "tags: [replicacion]\n---\n# Replicación de la base\n\nLa replicación usa un primario.\n",
        encoding="utf-8")
    return r


@pytest.mark.parametrize("argumento,valor", [
    ("--top-k", "0"), ("--top-k", "-1"),
    ("--excerpt-tokens", "0"), ("--excerpt-tokens", "-5"),
])
def test_un_tope_no_positivo_se_rechaza(raiz, argumento, valor):
    env = _run(raiz, "--query", "replicación", argumento, valor, "--budget", "4000")
    assert env["ok"] is False and env["error_code"] == "INVALID_INPUT", env
    assert argumento in env["message"]


def test_un_tope_positivo_empaqueta(raiz):
    env = _run(raiz, "--query", "replicación", "--top-k", "1", "--budget", "4000")
    assert env["ok"] is True, env
