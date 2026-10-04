"""Lo obligatorio que no es un `required=True` llega al catálogo MCP (AP-40).

Medido el 2026-10-04: `vault_write` publicaba `required: ["folder"]` y la
llamada `{folder}` llegaba al proceso hijo, que la rechazaba por falta de
`title`; `vault_preferences`, `vault_project`, `vault_undo`… declaran un grupo
excluyente obligatorio y su esquema no tenía un solo obligatorio. Las dos
formas viajan como `requires_one_of`, no como `anyOf` del `inputSchema`, que
la API de Claude rechaza en el nivel superior.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_mcp_catalog import REQUISITOS_EN_CODIGO, TOOLS_CATALOG  # noqa: E402

PUBLICADO = json.loads(
    (ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8")
)["tools"]
CON_ALTERNATIVAS = sorted(n for n, t in PUBLICADO.items() if t.get("requires_one_of"))


def _cli(script, argv, env=None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *argv],
                          capture_output=True, text=True, encoding="utf-8",
                          env=env, timeout=120)


def test_ningun_esquema_lleva_combinadores_en_el_nivel_superior():
    for nombre, tool in PUBLICADO.items():
        assert not {"anyOf", "oneOf", "allOf"} & set(tool["inputSchema"]), nombre


@pytest.mark.parametrize("nombre", CON_ALTERNATIVAS)
def test_cada_alternativa_nombra_params_publicados(nombre):
    props = PUBLICADO[nombre]["inputSchema"]["properties"]
    for restriccion in PUBLICADO[nombre]["requires_one_of"]:
        for alternativa in restriccion:
            for param in alternativa:
                assert param in props, (nombre, param)
                assert "obligatorio uno de" in props[param]["description"], (nombre, param)


@pytest.mark.parametrize("nombre", sorted(
    n for n in CON_ALTERNATIVAS if n not in REQUISITOS_EN_CODIGO))
def test_el_grupo_publicado_es_el_que_argparse_exige(nombre):
    """Criterio del consumidor: el mensaje de argparse sin ningún flag."""
    # Los `required=True` se rellenan para que argparse llegue a quejarse del grupo.
    obligatorios = PUBLICADO[nombre]["inputSchema"].get("required", [])
    r = _cli(TOOLS_CATALOG[nombre]["script"],
             [x for p in obligatorios for x in (f"--{p}", "x")])
    m = re.search(r"one of the arguments (.+?) is required", r.stdout + r.stderr)
    assert m, (r.stdout[-300:], r.stderr[-300:])
    exigidos = {f.lstrip("-").split("/")[0] for f in m.group(1).split()}
    publicados = {alt[0] for alt in PUBLICADO[nombre]["requires_one_of"][0]}
    assert publicados == exigidos


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("alternativas")
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_AGENT="probe",
               PYTHONIOENCODING="utf-8")
    _cli("vault_init.py", [], env)
    return env


@pytest.mark.parametrize("nombre,argv", [
    ("vault_write", ["--folder", "07_Knowledge", "--tags", "x"]),
    ("vault_knowledge_save", ["--category", "concept"]),
])
def test_el_requisito_en_codigo_es_uno_que_la_cli_exige(entorno, nombre, argv):
    """Una entrada de REQUISITOS_EN_CODIGO que la CLI no exige sería un
    obligatorio inventado: el servidor rechazaría una llamada válida."""
    assert nombre in REQUISITOS_EN_CODIGO
    r = _cli(TOOLS_CATALOG[nombre]["script"], argv, entorno)
    assert '"ok": true' not in r.stdout, r.stdout[-300:]
    assert r.returncode != 0 or '"ok": false' in r.stdout, (r.stdout[-300:], r.stderr[-300:])
