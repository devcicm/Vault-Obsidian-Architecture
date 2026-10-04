"""La acción que sugiere `vault_audit` para una sección vacía se ejecuta (AP-42).

Medido el 2026-10-04 ejecutando cada pista contra un vault recién creado:
doce de veinte salían con `INVALID_ARGS` por faltarles un flag obligatorio
(`--trigger`, `--description`, `--symptom`…), la de `16_AI_Governance` pedía
`--decision_type architecture`, que no está en `DECISION_TYPES`, y el comando
devuelto era `python scripts/vault_pattern_save`, sin `.py`, que ni arranca.
La sugerencia de un audit es lo que el usuario copia y pega: un ejemplo que
sale con exit 2 enseña a desconfiar de la tool en vez de a usarla.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_audit  # noqa: E402
from vault_registry import SECTIONS  # noqa: E402

# Lo que el usuario rellena él mismo. Una pista puede fallar por el contenido
# de relleno (`content_too_short`), nunca porque argparse la rechace.
RECHAZO_DE_FORMA = {"INVALID_ARGS", "INVALID_VALUE", "MISSING_ARGUMENT"}


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("pistas")
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_AGENT="probe",
               PYTHONIOENCODING="utf-8")
    for argv in (["vault_init.py"], ["vault_project.py", "--add", "demo"]):
        subprocess.run([sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
                       capture_output=True, env=env, timeout=300, check=True)
    fuente = raiz.parent / "fuente.md"
    fuente.write_text("# Fuente\n\nTexto de prueba.\n", encoding="utf-8")
    return env, fuente


def _rellenar(comando, fuente):
    c = comando.replace("<slug>", "demo").replace(
        "<path>", shlex.quote(fuente.as_posix()))
    c = c.replace("$(date +%Y-%m-%d)", "2026-10-04")
    c = c.replace("'...'", "'Texto de prueba suficiente para la pista.'")
    return re.sub(r"<([^>]+)>", r"\1", c)


@pytest.mark.parametrize("folder", [s["folder"] for s in SECTIONS])
def test_la_pista_de_cada_seccion_arranca_y_pasa_argparse(entorno, folder):
    env, fuente = entorno
    comando = vault_audit._suggest_command_for_folder(folder)
    argv = shlex.split(_rellenar(comando, fuente))
    assert argv[:2] == ["python", argv[1]] and argv[1].endswith(".py"), comando
    script = ROOT / argv[1]
    assert script.is_file(), comando
    r = subprocess.run([sys.executable, str(script), *argv[2:]], capture_output=True,
                       text=True, encoding="utf-8", env=env, timeout=300)
    assert r.returncode != 2, (comando, r.stdout[-400:], r.stderr[-400:])
    try:
        sobre = json.loads(r.stdout)
    except ValueError:
        sobre = {}
    assert sobre.get("error_code") not in RECHAZO_DE_FORMA, (comando, sobre)
