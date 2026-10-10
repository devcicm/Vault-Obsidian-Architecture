"""AP-47 — quitar una nota de su sección también la quita de su `index.md`.

Medido como consumidor el 2026-10-10: el índice de sección se rehace en el
gancho de escritura (`atomic_write_text`), y ni el `unlink` de `vault_delete`
ni la salida de una nota con `vault_move` escriben en la carpeta de origen.
El `index.md` seguía enlazando la nota que ya no estaba: un enlace roto que el
propio vault había generado. `vault_io.refrescar_indice_de_seccion` es el
mismo refresco, para quien quita en vez de escribir.
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

CUERPO = "\n".join(f"Linea {i} con cuerpo suficiente para el gate de contenido." for i in range(4))


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "03_Decisions"):
        (r / seccion).mkdir(parents=True)
    for titulo in ("Se queda", "Se va"):
        env = _run(r, "vault_write.py", "--folder", "07_Knowledge", "--title", titulo,
                   "--content", CUERPO, "--tags", "t1")
        assert env["ok"] is True, env
    indice = (r / "07_Knowledge" / "index.md").read_text(encoding="utf-8")
    assert "se-va" in indice and "se-queda" in indice, indice
    return r


def test_delete_saca_la_nota_del_indice(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/se-va.md", "--reason", "prueba")
    assert env["ok"] is True, env
    indice = (raiz / "07_Knowledge" / "index.md").read_text(encoding="utf-8")
    assert "se-va" not in indice and "se-queda" in indice, indice


def test_move_saca_la_nota_del_indice_de_origen(raiz):
    env = _run(raiz, "vault_move.py", "--from", "07_Knowledge/se-va.md",
               "--to", "03_Decisions/se-va.md", "--type", "decision", "--json")
    assert env["ok"] is True, env
    indice = (raiz / "07_Knowledge" / "index.md").read_text(encoding="utf-8")
    assert "se-va" not in indice and "se-queda" in indice, indice
    destino = (raiz / "03_Decisions" / "index.md").read_text(encoding="utf-8")
    assert "se-va" in destino, destino
