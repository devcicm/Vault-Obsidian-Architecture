"""AP-36 — `vault_list --folder` no lista notas de fuera del vault.

Medido como consumidor el 2026-10-10: `vault_list --folder ../afuera` devolvía
`ok: true` con las notas de una carpeta hermana del vault, rutas `../` incluidas.
Por `vault run` lo paraba el pre-flight de la CLI, pero el script —que es lo que
ejecuta el servidor MCP— no comprobaba nada: leer fuera del vault es el mismo
escape que escribir fuera, solo que en silencio.
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


def _nota(titulo: str) -> str:
    return f"---\ntitle: {titulo}\nstatus: draft\ntype: knowledge\n---\n# {titulo}\n"


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "07_Knowledge").mkdir(parents=True)
    (r / "07_Knowledge" / "dentro.md").write_text(_nota("dentro"), encoding="utf-8")
    (tmp_path / "afuera").mkdir()
    (tmp_path / "afuera" / "secreto.md").write_text(_nota("secreto"), encoding="utf-8")
    return r


@pytest.mark.parametrize("carpeta", ["../afuera", "07_Knowledge/../../afuera"])
def test_list_rechaza_una_carpeta_fuera_del_vault(raiz, carpeta):
    env = _run(raiz, "--folder", carpeta)
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env
    assert "secreto" not in json.dumps(env)


def test_list_rechaza_una_ruta_absoluta(raiz, tmp_path):
    env = _run(raiz, "--folder", str(tmp_path / "afuera"))
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env


def test_list_sigue_listando_dentro(raiz):
    env = _run(raiz, "--folder", "07_Knowledge/../07_Knowledge")
    assert env["ok"] is True
    assert [n["path"] for n in env["notes"]] == ["07_Knowledge/dentro.md"]
