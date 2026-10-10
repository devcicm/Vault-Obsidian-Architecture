"""AP-14 — `vault_delete` dice qué notas quedan con un enlace roto.

Medido como consumidor el 2026-10-10: borrar una nota enlazada devolvía
`ok: true` sin una palabra, y las notas que la enlazaban quedaban apuntando a
nada. No se rechaza —borrar es una decisión del agente—, pero el sobre lista
`inbound_links` con el mismo criterio con el que `vault_move` las reescribe
(`notas_que_enlazan`, AP-57): por nombre de fichero y sufijo de ruta, como
Obsidian (AP-44). En `--dry-run` también, que es cuando sirve.
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
    k = r / "07_Knowledge"
    k.mkdir()
    (k / "objetivo.md").write_text(_nota("objetivo", "sin enlaces"), encoding="utf-8")
    (k / "a.md").write_text(_nota("a", "ver [[objetivo]]"), encoding="utf-8")
    (k / "b.md").write_text(_nota("b", "ver [[07_Knowledge/Objetivo.md#parte|alias]]"), encoding="utf-8")
    (k / "c.md").write_text(_nota("c", "nada que ver con [[otra]]"), encoding="utf-8")
    return r


def test_delete_lista_quien_la_enlaza(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/objetivo.md", "--reason", "prueba")
    assert env["ok"] is True, env
    assert env["inbound_links"] == ["07_Knowledge/a.md", "07_Knowledge/b.md"], env


def test_dry_run_lo_anuncia_sin_borrar(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/objetivo.md",
               "--reason", "prueba", "--dry-run")
    assert env["ok"] is True, env
    assert env["inbound_links"] == ["07_Knowledge/a.md", "07_Knowledge/b.md"], env
    assert (raiz / "07_Knowledge" / "objetivo.md").is_file()


def test_sin_entrantes_la_lista_esta_vacia(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/c.md", "--reason", "prueba")
    assert env["ok"] is True and env["inbound_links"] == [], env
