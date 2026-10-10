"""AP-46 / AP-37 — `vault_append --section` escribe donde dice que escribe.

Medido como consumidor el 2026-10-10, todos con `ok: true`:

- `--section "## Notas"` escribía bajo «## Notas finales»: la sección se
  buscaba como prefijo, no como encabezado (también casaba «### Notas»).
- Una sección que no existía añadía el texto al final, bajo la última
  sección de la nota, y el sobre devolvía `section: "## Inexistente"`.
- Un `--content` vacío o de espacios devolvía `ok: true`; el de espacios
  dejaba líneas en blanco.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
NOTA = ("---\ntitle: n\nstatus: draft\ntype: knowledge\n---\n# n\n\n"
        "## Notas finales\n\nuno\n\n### Notas\n\nsub\n\n## Notas\n\ndos\n\n## Cierre\n\nfin\n")


def _append(raiz: Path, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_append.py"), "--path",
                        "07_Knowledge/n.md", "--no-timestamp", *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    (r / "07_Knowledge" / "n.md").write_text(NOTA, encoding="utf-8")
    return r


def _nota(raiz: Path) -> str:
    return (raiz / "07_Knowledge" / "n.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("seccion", ["## Notas", "Notas"])
def test_la_seccion_es_el_encabezado_exacto(raiz, seccion):
    # AP-46: «## Notas» no es «## Notas finales» ni «### Notas».
    env = _append(raiz, "--content", "NUEVO", "--section", seccion)
    assert env["ok"] is True, env
    texto = _nota(raiz)
    assert texto.index("NUEVO") > texto.index("\n## Notas\n")
    assert texto.index("NUEVO") < texto.index("## Cierre")


def test_una_seccion_que_no_existe_se_crea(raiz):
    env = _append(raiz, "--content", "NUEVO", "--section", "## Pendientes")
    assert env["ok"] is True and env["section_created"] is True, env
    texto = _nota(raiz)
    assert texto.rstrip().endswith("## Pendientes\n\nNUEVO")
    assert texto.startswith(NOTA.rstrip("\n"))


def test_una_seccion_que_existe_no_se_marca_creada(raiz):
    env = _append(raiz, "--content", "NUEVO", "--section", "## Cierre")
    assert env["ok"] is True and env["section_created"] is False, env


@pytest.mark.parametrize("contenido", ["", "   ", "\n\n"])
def test_el_contenido_vacio_se_rechaza(raiz, contenido):
    # AP-37: un append sin nada que añadir no es un append.
    env = _append(raiz, "--content", contenido)
    assert env["ok"] is False and env["error_code"] == "INVALID_INPUT", env
    assert _nota(raiz) == NOTA
