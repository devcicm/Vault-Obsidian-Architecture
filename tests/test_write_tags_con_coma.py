"""AP-26 / AP-39 — `--tags "a,b"` son dos tags, como enseña la propia ayuda.

Medido como consumidor el 2026-10-10: el docstring de `vault_write` documenta
`--tags "architecture,backend"`, pero `--tags` es `nargs="*"` y la coma llegaba
dentro de un solo valor; la normalización de AP-39 la convertía en guion y la
nota quedaba con UNA tag, `architecture-backend`, que ningún filtro por
`architecture` ni por `backend` encuentra. Obsidian no admite comas en una tag,
así que partir por coma no le quita nada a ninguna.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CUERPO = "Texto propio de la nota, linea uno.\nTexto propio dos con palabras.\nTexto propio tres."


def _write(raiz: Path, *tags: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_write.py"), "--folder",
                        "07_Knowledge", "--title", "Nota", "--content", CUERPO,
                        "--agent", "test", "--tags", *tags],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


def _tags(raiz: Path) -> list:
    texto = (raiz / "07_Knowledge" / "nota.md").read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---")[1])["tags"]


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    return r


@pytest.mark.parametrize("args", [("architecture,backend",), ("architecture, backend",),
                                  ("architecture", "backend"), ("architecture,", "backend")])
def test_la_coma_separa_tags(raiz, args):
    env = _write(raiz, *args)
    assert env["ok"] is True, env
    assert _tags(raiz) == ["architecture", "backend"]


def test_solo_comas_no_son_tags(raiz):
    # AP-26: `--tags ","` no es una tag; se pide como si faltara.
    env = _write(raiz, ",")
    assert env["ok"] is False and env["error_code"] == "missing_tags", env
