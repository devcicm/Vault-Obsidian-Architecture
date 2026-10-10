"""AP-36 / CN-02 — mover una nota la deja siendo una nota.

Medido como consumidor el 2026-10-10: `vault_move --from 07_Knowledge/n.md
--to 07_Knowledge/n.txt` (o sin extensión) devolvía `ok: true`. La nota salía
del vault por la puerta de la extensión: ningún lector la ve, sus enlaces
entrantes quedaban reescritos hacia un fichero que Obsidian no resuelve como
nota, y nada lo avisaba. El destino de una nota `.md` tiene que ser `.md`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEXTO = "---\ntitle: n\nstatus: draft\ntype: knowledge\n---\n# n\n\ncuerpo\n"


def _move(raiz: Path, origen: str, destino: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_move.py"), "--from", origen,
                        "--to", destino, "--json"],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    (r / "07_Knowledge" / "n.md").write_text(TEXTO, encoding="utf-8")
    return r


@pytest.mark.parametrize("destino", ["07_Knowledge/n.txt", "07_Knowledge/n",
                                     "07_Knowledge/n.md.bak"])
def test_una_nota_no_se_mueve_a_un_fichero_que_no_es_nota(raiz, destino):
    # AP-36: el destino de una nota `.md` es `.md`; el origen queda intacto.
    env = _move(raiz, "07_Knowledge/n.md", destino)
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env
    assert (raiz / "07_Knowledge" / "n.md").read_text(encoding="utf-8") == TEXTO
    assert not (raiz / destino).exists()


def test_la_extension_en_mayusculas_sigue_siendo_nota(raiz):
    env = _move(raiz, "07_Knowledge/n.md", "07_Knowledge/m.MD")
    assert env["ok"] is True, env
