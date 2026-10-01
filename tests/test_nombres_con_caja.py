"""Los ficheros que el código abre por nombre existen con esa misma caja en git.

Medido en v40.34: el índice guardaba `agents.md` y treinta y tantos sitios
—`vault_gate --check-doc`, `vault_doc_counts`, `vault_servicio`, el Makefile—
abren `AGENTS.md`. En Windows y macOS el sistema de ficheros no distingue y
todo sale verde; en el checkout de Linux de un tercero, o de la CI, el fichero
no existe. Medir en la máquina que no distingue mayúsculas es medir con el
criterio propio (AP-44): el consumidor es el checkout, no este disco.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

#: Nombres que el código abre literalmente desde la raíz del repo.
ABIERTOS_POR_NOMBRE = ("AGENTS.md", "README.md", "pyproject.toml", "Makefile")


def _indice_de_git():
    if not shutil.which("git") or not (RAIZ / ".git").exists():
        pytest.skip("sin checkout de git")
    salida = subprocess.run(
        ["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return set(filter(None, salida.split("\0")))


@pytest.mark.parametrize("nombre", ABIERTOS_POR_NOMBRE)
def test_el_indice_guarda_la_caja_que_el_codigo_abre(nombre):
    indice = _indice_de_git()
    otras = sorted(p for p in indice if p.lower() == nombre.lower() and p != nombre)
    assert nombre in indice, (
        f"git guarda {otras or 'nada'} y el código abre {nombre}: "
        "en un sistema de ficheros que distingue mayúsculas no existe"
    )
