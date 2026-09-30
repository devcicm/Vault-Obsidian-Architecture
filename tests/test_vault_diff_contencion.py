"""AP-36 — `vault_diff` no lee ficheros fuera del vault.

Medido antes del arreglo: `--compare` y `--with` aceptaban una ruta absoluta o
con `..` y devolvían el contenido **línea a línea** en los hunks; `--hash`
publicaba el tamaño y la huella de cualquier fichero legible, y una ruta
relativa que no existiera en el vault se buscaba además en `scripts/`. Por MCP
eso es leer el disco del usuario desde una sesión que solo debía ver su vault.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SECRETO = "linea-secreta-fuera-del-vault"


def _ejecutar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_diff.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    (raiz / "07_Knowledge" / "a.md").write_text("uno\ndos\n", encoding="utf-8")
    (raiz / "07_Knowledge" / "b.md").write_text("uno\ntres\n", encoding="utf-8")
    canario = tmp_path / "canario.txt"
    canario.write_text(f"{SECRETO}\n", encoding="utf-8")
    return raiz, canario


@pytest.mark.parametrize("forma", ["relativa", "absoluta"])
@pytest.mark.parametrize("modo", ["compare", "with", "hash", "path"])
def test_ap36_una_ruta_fuera_del_vault_se_rechaza(entorno, forma, modo):
    raiz, canario = entorno
    fuera = "../canario.txt" if forma == "relativa" else str(canario)
    argv = {
        "compare": ["--compare", fuera, "--with", "07_Knowledge/a.md"],
        "with": ["--compare", "07_Knowledge/a.md", "--with", fuera],
        "hash": ["--hash", fuera],
        "path": ["--path", fuera],
    }[modo]

    env = _ejecutar(raiz, *argv)

    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env
    assert SECRETO not in json.dumps(env)


def test_una_ruta_de_scripts_no_se_resuelve(entorno):
    """El fallback a `scripts/` leía el toolkit con una ruta «relativa al vault»."""
    raiz, _ = entorno
    env = _ejecutar(raiz, "--hash", "vault_diff.py")
    # Antes salía FILE_READ_ERROR: el fichero de `scripts/` se había leído y
    # solo fallaba al intentar expresarlo relativo al vault.
    assert env["ok"] is False and env["error_code"] == "FILE_NOT_FOUND", env


def test_dos_notas_del_vault_se_comparan(entorno):
    raiz, _ = entorno
    env = _ejecutar(raiz, "--compare", "07_Knowledge/a.md", "--with", "07_Knowledge/b.md")
    assert env["ok"] is True and env["changed"] is True, env
    assert env["compared_a"] == "07_Knowledge/a.md"


def test_una_ruta_absoluta_dentro_del_vault_sigue_valiendo(entorno):
    raiz, _ = entorno
    env = _ejecutar(raiz, "--hash", str(raiz / "07_Knowledge" / "a.md"))
    assert env["ok"] is True and env["path"] == "07_Knowledge/a.md", env
