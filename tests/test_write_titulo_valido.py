"""CN-01 / AP-02 — un título tiene que poder ser el nombre de una nota visible.

Medido como consumidor el 2026-10-10, todos con `ok: true`:

- «.», «..» y «...» producían `..md`, `...md` y `....md`. Obsidian no muestra
  un fichero que empieza por punto: la nota existía y nadie la veía.
- «   » y «-» no dejan un solo carácter para el nombre y caían a `untitled.md`,
  un nombre inventado que comparten todos los títulos sin letras; el segundo
  pisaba al primero (AP-02 lo para desde G9, pero el nombre ya era inventado).
- «a⏎b» guardaba un salto de línea dentro de `title:`, que ningún enlace puede
  escribir.
- «  Hola  » guardaba los espacios de los bordes en el `title`.
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


def _write(raiz: Path, titulo: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_write.py"), "--folder",
                        "07_Knowledge", "--title", titulo, "--content", CUERPO,
                        "--tags", "prueba", "--agent", "test"],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    return r


@pytest.mark.parametrize("titulo", [".", "..", "...", "   ", "-", "a\nb", "a\tb", "a\rb"])
def test_un_titulo_sin_nombre_posible_se_rechaza(raiz, titulo):
    # CN-01: ni nombre oculto, ni nombre inventado, ni control dentro del título.
    env = _write(raiz, titulo)
    # `a\rb` ya lo paraba el CLI antes con ENCODING_ERROR (regla previa).
    assert env["ok"] is False and env["error_code"] in ("INVALID_INPUT", "ENCODING_ERROR"), env
    assert [p.name for p in (raiz / "07_Knowledge").iterdir()] == []


def test_los_espacios_de_los_bordes_no_son_parte_del_titulo(raiz):
    env = _write(raiz, "  Hola  ")
    assert env["ok"] is True, env
    texto = (raiz / "07_Knowledge" / "hola.md").read_text(encoding="utf-8")
    assert yaml.safe_load(texto.split("---")[1])["title"] == "Hola"


@pytest.mark.parametrize("titulo,fichero", [("untitled", "untitled.md"), ("!!!", "!!!.md")])
def test_los_titulos_que_ya_tenian_nombre_lo_conservan(raiz, titulo, fichero):
    # No-derogación: `!!!` conserva el nombre heredado que documenta `slugify`.
    env = _write(raiz, titulo)
    assert env["ok"] is True, env
    assert (raiz / "07_Knowledge" / fichero).exists()
