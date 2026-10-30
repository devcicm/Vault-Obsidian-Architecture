"""D-04 — borrar o mover una nota también cuida los índices de dominio.

`vault_delete` ya quita la nota de `search-index.json` y `vault_move` reescribe
su ruta, pero los índices `18_Bugs/.bugs-index.json`, `11_Code/.code-index.json`,
`14_Requirements/.requirements-index.json`... guardan la nota por `relPath` y
nadie los tocaba: la entrada quedaba apuntando a un fichero que ya no estaba
(delete) o a la ruta vieja (move). Los consumidores del índice —el guard AP-17
de `vault_code_module`, la identidad por ruta de `vault_bug_save`— leían esa
ruta muerta.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CUERPO = "\n".join(f"Linea {i} con cuerpo suficiente para el gate de contenido." for i in range(4))


def _run(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


def _indice(raiz: Path) -> Path:
    return raiz / "18_Bugs" / ".bugs-index.json"


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "03_Decisions", "18_Bugs"):
        (r / seccion).mkdir(parents=True)
    for titulo in ("Se queda", "Se va"):
        env = _run(r, "vault_write.py", "--folder", "07_Knowledge", "--title", titulo,
                   "--content", CUERPO, "--tags", "t1")
        assert env["ok"] is True, env
    _indice(r).write_text(json.dumps({"bugs": [
        {"docId": "a", "bug_id": "BUG-001", "relPath": "07_Knowledge/se-queda.md"},
        {"docId": "b", "bug_id": "BUG-002", "relPath": "07_Knowledge/se-va.md"},
    ]}), encoding="utf-8")
    return r


def _rutas(raiz: Path) -> list:
    return [b["relPath"] for b in json.loads(_indice(raiz).read_text(encoding="utf-8"))["bugs"]]


def test_delete_quita_la_entrada_del_indice_de_dominio(raiz):
    env = _run(raiz, "vault_delete.py", "--path", "07_Knowledge/se-va.md", "--reason", "prueba")
    assert env["ok"] is True, env
    assert _rutas(raiz) == ["07_Knowledge/se-queda.md"]


def test_move_reescribe_la_ruta_en_el_indice_de_dominio(raiz):
    env = _run(raiz, "vault_move.py", "--from", "07_Knowledge/se-va.md",
               "--to", "03_Decisions/se-va.md", "--type", "decision", "--json")
    assert env["ok"] is True, env
    assert _rutas(raiz) == ["07_Knowledge/se-queda.md", "03_Decisions/se-va.md"]
