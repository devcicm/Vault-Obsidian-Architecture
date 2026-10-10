"""AP-47 — `vault_delete` no borra un artefacto derivado.

Medido como consumidor el 2026-10-10: `vault_delete --path 07_Knowledge/index.md`
devolvía `ok: true` y dejaba la sección sin índice, con una entrada `deleted`
en el change-log para algo que no es una nota. El `index.md` lo escribe y lo
rehace su generador (`es_artefacto_derivado`); borrarlo a mano es el desfase
que AP-47 nombra, y SP-01 es el protocolo de borrado de **notas**.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


def _nota(titulo: str, cuerpo: str) -> str:
    return f"---\ntitle: {titulo}\nstatus: draft\ntype: knowledge\n---\n# {titulo}\n\n{cuerpo}\n"


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    (r / "07_Knowledge" / "nota.md").write_text(_nota("nota", "cuerpo"), encoding="utf-8")
    (r / "07_Knowledge" / "index.md").write_text("# 07_Knowledge\n\n- [[nota]]\n", encoding="utf-8")
    return r


@pytest.mark.parametrize("ruta", ["07_Knowledge/index.md", "07_Knowledge/../07_Knowledge/index.md"])
def test_delete_rechaza_el_indice_de_seccion(raiz, ruta):
    env = _run(raiz, "vault_delete.py", "--path", ruta, "--reason", "prueba")
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env
    assert "AP-47" in env["message"]
    assert (raiz / "07_Knowledge" / "index.md").is_file()
    assert not (raiz / "00_System" / ".change-log.json").exists()


def test_delete_dry_run_tampoco_lo_acepta(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/index.md",
               "--reason", "prueba", "--dry-run")
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env


def test_una_nota_se_sigue_borrando(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/nota.md", "--reason", "prueba")
    assert env["ok"] is True and env["action"] == "deleted", env
