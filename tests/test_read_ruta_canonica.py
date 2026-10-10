"""AP-51 — `vault_read` devuelve la ruta canónica y su historial con cualquier grafía.

Medido como consumidor el 2026-10-10: `vault_read --path ./07_Knowledge//Nota.md`
(o `07_knowledge/nota.MD` en Windows, o con un `..` de ida y vuelta) leía la
nota y devolvía `path` tal como llegó. El agente que guarda ese `path` como
identidad tiene dos para la misma nota, y el historial se buscaba con la clave
cruda: `historyVersions: []` con ok:true, indistinguible de una nota sin
versiones.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CONTENIDO = ("Primera línea con palabras suficientes para la norma." + "\n"
             + "Segunda línea que describe la nota con algo de detalle." + "\n"
             + "Tercera línea para que el contenido no sea un esqueleto.")


def _run(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


@pytest.fixture(scope="module")
def raiz(tmp_path_factory):
    r = tmp_path_factory.mktemp("vr") / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    for texto in (CONTENIDO, CONTENIDO + "\nCuarta línea: la segunda versión cambia el cuerpo de verdad."):
        env = _run(r, "vault_write.py", "--folder", "07_Knowledge", "--title", "Nota",
                   "--content", texto, "--tags", "prueba")
        assert env["ok"], env
    return r


@pytest.fixture(scope="module")
def canonica(raiz):
    env = _run(raiz, "vault_read.py", "--path", "07_Knowledge/nota.md")
    assert env["ok"] and env["historyVersions"], env
    return env


VARIANTES = ["./07_Knowledge//nota.md", "07_Knowledge/../07_Knowledge/nota.md"]
if os.name == "nt":  # separador y caja solo designan la misma nota en Windows
    VARIANTES += ["07_Knowledge\\nota.md", "07_KNOWLEDGE/NOTA.md"]


@pytest.mark.parametrize("variante", VARIANTES)
def test_cualquier_grafia_devuelve_la_misma_identidad(raiz, canonica, variante):
    env = _run(raiz, "vault_read.py", "--path", variante)
    assert env["ok"], env
    assert env["path"] == canonica["path"] == "07_Knowledge/nota.md"
    assert env["historyVersions"] == canonica["historyVersions"]
