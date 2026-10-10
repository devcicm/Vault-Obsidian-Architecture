"""CIA-A / SP-01 — una nota borrada con `vault_delete` se puede recuperar.

Medido como consumidor el 2026-10-10: `vault_delete` (sin `--trash-only`) hacía
`unlink` y devolvía `ok: true`. La única copia era la de `.history/` que hubiese
dejado una escritura anterior —si la había—, y `vault_undo --restore` contestaba
`NOTE_NOT_FOUND` porque exigía que la nota existiera: el borrado era definitivo
justo por la tool cuyo oficio es deshacer. El borrado guarda ahora la versión
que borra, y `vault_undo` la devuelve a su sitio.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEXTO = "---\ntitle: borrable\nstatus: draft\ntype: knowledge\n---\n# borrable\n\ncontenido unico 4711\n"


def _run(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    (r / "07_Knowledge" / "borrable.md").write_text(TEXTO, encoding="utf-8")
    return r


def test_delete_guarda_la_version_que_borra(raiz):
    # CIA-A: lo borrado queda en `.history/` y el sobre dice cómo volver.
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/borrable.md",
               "--reason", "prueba")
    assert env["ok"] is True and env["action"] == "deleted", env
    assert not (raiz / "07_Knowledge" / "borrable.md").exists()
    guardada = raiz / ".history" / env["recoverable"]["history"]
    assert guardada.read_text(encoding="utf-8") == TEXTO
    assert "vault_undo" in env["recoverable"]["restore"]


def test_undo_restaura_una_nota_borrada(raiz):
    _run(raiz, "vault_delete.py", "--path", "07_Knowledge/borrable.md", "--reason", "prueba")
    env = _run(raiz, "vault_undo.py", "--restore", "07_Knowledge/borrable.md")
    assert env["ok"] is True and env["action"] == "restored_deleted", env
    assert (raiz / "07_Knowledge" / "borrable.md").read_text(encoding="utf-8") == TEXTO


def test_undo_lista_las_versiones_de_una_nota_borrada(raiz):
    _run(raiz, "vault_delete.py", "--path", "07_Knowledge/borrable.md", "--reason", "prueba")
    env = _run(raiz, "vault_undo.py", "--list", "07_Knowledge/borrable.md")
    assert env["ok"] is True and env["total"] == 1, env


def test_delete_dry_run_no_guarda_nada(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/borrable.md",
               "--reason", "prueba", "--dry-run")
    assert env["ok"] is True, env
    assert not (raiz / ".history").exists()
