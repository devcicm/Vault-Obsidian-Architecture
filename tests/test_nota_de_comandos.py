"""La nota de comandos que se reparte a cada vault corre tal y como se publica (AP-42).

Medido el 2026-10-04 en la QA de producto: `00_System/vault-commands.md` se
declara «referencia única de comandos», pero publicaba `python scripts/...`,
que en una instalación por wheel no existe; citaba `--init v32`, catorce
versiones atrás; incluía `vault_spec_validate`, que no es una tool instalable,
y su lista por sección —escrita a mano, solo 01–16— daba a once secciones un
comando al que le faltaban flags obligatorios. Las secciones 17–21 no estaban.

El test lee la nota que se genera, no el registro: es lo que copia quien la
abre (AP-44).
"""

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_section_index  # noqa: E402
from vault.meta_toolkit.resolucion_producto import INSTALLED, resolver_producto  # noqa: E402
from vault_registry import SECTIONS, comando_de_tool  # noqa: E402

RECHAZO_DE_FORMA = {"INVALID_ARGS", "INVALID_VALUE", "MISSING_ARGUMENT"}


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("comandos")
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_AGENT="probe",
               PYTHONIOENCODING="utf-8")
    for argv in (["vault_init.py"], ["vault_project.py", "--add", "demo"]):
        subprocess.run([sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
                       capture_output=True, env=env, timeout=300, check=True)
    fuente = raiz.parent / "fuente.md"
    fuente.write_text("# Fuente\n\nTexto de prueba.\n", encoding="utf-8")
    nota = (raiz / "00_System" / "vault-commands.md").read_text(encoding="utf-8")
    return env, fuente, nota


def _comandos(nota):
    """Cada comando que la nota publica, en orden: una fila de lista por comando."""
    return [m.group(1) for m in re.finditer(r"^- .+? — `(.+)`$", nota, re.M)]


def _rellenar(comando, fuente):
    c = comando.replace("<slug>", "demo").replace(
        "<path>", shlex.quote(fuente.as_posix()))
    c = c.replace("$(date +%Y-%m-%d)", "2026-10-04")
    c = c.replace("'...'", "'Texto de prueba suficiente para la nota de comandos.'")
    return re.sub(r"<([^>]+)>", r"\1", c)


def test_la_nota_publica_lo_que_declara_el_registro(vault):
    _, _, nota = vault
    esperados = [comando_de_tool(r)
                 for r in vault_section_index.recetas_de_la_nota_de_comandos()]
    assert _comandos(nota) == esperados


def test_la_lista_por_seccion_cubre_toda_seccion_con_receta(vault):
    _, _, nota = vault
    for s in SECTIONS:
        if s["tool_hint"]:
            assert f"- **{s['folder']}** — `" in nota, s["folder"]
    assert "--init v" not in nota and "--to v" not in nota


def test_toda_tool_de_la_nota_corre_en_la_instalacion(vault):
    """La forma `vault run` solo sirve si la tool está en la wheel."""
    _, _, nota = vault
    for comando in _comandos(nota):
        tool = Path(shlex.split(comando)[1]).stem
        assert resolver_producto(tool).estado == INSTALLED, comando


def test_cada_comando_de_la_nota_pasa_argparse(vault):
    env, fuente, nota = vault
    fallos = []
    for comando in _comandos(nota):
        argv = shlex.split(_rellenar(comando, fuente))
        assert argv[0] == "python" and argv[1].endswith(".py"), comando
        r = subprocess.run([sys.executable, str(ROOT / argv[1]), *argv[2:]],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=300)
        try:
            sobre = json.loads(r.stdout)
        except ValueError:
            sobre = {}
        if r.returncode == 2 or sobre.get("error_code") in RECHAZO_DE_FORMA:
            fallos.append((comando, r.stderr[-300:], sobre.get("message")))
    assert fallos == [], fallos


def test_instalado_la_receta_sale_como_vault_run(tmp_path):
    """En la wheel el registro vive en `vault_toolkit/_impl/`, sin `scripts/`."""
    impl = tmp_path / "_impl"
    impl.mkdir()
    shutil.copy(SCRIPTS / "vault_registry.py", impl / "vault_registry.py")
    spec = importlib.util.spec_from_file_location("registro_instalado",
                                                  impl / "vault_registry.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    assert modulo.comando_de_tool("vault_audit") == "vault run vault_audit"
    assert (modulo.comando_de_tool("vault_tags --audit")
            == "vault run vault_tags --audit")
    assert comando_de_tool("vault_tags --audit") == "python scripts/vault_tags.py --audit"
