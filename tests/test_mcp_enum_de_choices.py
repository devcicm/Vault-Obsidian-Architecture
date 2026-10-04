"""Todo `choices=` de la CLI llega al esquema MCP como `enum` (AP-48).

Medido el 2026-10-04: de los 50 `choices=` de las tools del catálogo, solo
los 15 escritos como lista literal salían en `tools-catalog.json`. Los otros
35 —`CATEGORIES`, `list(TYPE_FOLDERS.keys())`, `_opciones("severidad")`—
se publicaban como `string` libre, así que un cliente que validaba contra el
esquema mandaba cualquier valor y solo se enteraba por el exit 2 de argparse.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402

PUBLICADO = json.loads(
    (ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8")
)["tools"]


def _sitios_con_choices():
    for nombre, tool in sorted(TOOLS_CATALOG.items()):
        script = tool.get("script")
        if nombre not in PUBLICADO or not script or not (SCRIPTS / script).is_file():
            continue
        arbol = ast.parse((SCRIPTS / script).read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
                continue
            largos = [a.value for a in nodo.args
                      if isinstance(a, ast.Constant) and str(a.value).startswith("--")]
            if largos and any(k.arg == "choices" for k in nodo.keywords):
                yield nombre, script, largos[0]


SITIOS = list(_sitios_con_choices())


def test_hay_choices_no_literales_que_medir():
    # Sin esto el test de abajo pasaría vacío si el recorrido dejara de verlos.
    assert len(SITIOS) >= 40, len(SITIOS)


@pytest.mark.parametrize("nombre,script,flag", SITIOS)
def test_cada_choices_se_publica_como_enum(nombre, script, flag):
    prop = PUBLICADO[nombre]["inputSchema"]["properties"].get(flag[2:])
    assert prop is not None, (nombre, flag)
    assert prop.get("enum"), (nombre, flag, prop)


@pytest.mark.parametrize("nombre,script,flag", [
    ("vault_knowledge_save", "vault_knowledge_save.py", "--category"),
    ("vault_log_error", "vault_log_error.py", "--type"),
    ("vault_bug_save", "vault_bug_save.py", "--severity"),
    ("vault_risk_save", "vault_risk_save.py", "--impact"),  # entero: se le da 9
])
def test_el_enum_es_lo_que_argparse_acepta(nombre, script, flag):
    """Criterio del consumidor (AP-44): no la expresión evaluada por el
    catálogo, sino la lista que argparse enseña al rechazar un valor."""
    r = subprocess.run([sys.executable, str(SCRIPTS / script), flag,
                        "9" if flag == "--impact" else "__no_vale__"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    m = re.search(r"choose from (.+?)\)", r.stdout + r.stderr)
    assert m, (r.stdout[-300:], r.stderr[-300:])
    # Python 3.14 los cita y las anteriores no: se normalizan las dos formas.
    aceptados = [v.strip().strip("'") for v in m.group(1).split(",")]
    publicado = PUBLICADO[nombre]["inputSchema"]["properties"][flag[2:]]["enum"]
    assert [str(v) for v in publicado] == aceptados


def test_el_enum_de_un_entero_son_enteros():
    """`vault_risk_save --impact` publicaba `low..critical` sobre un `integer`
    que la CLI acepta como 1-5: ningún valor válido cumplía el esquema."""
    props = PUBLICADO["vault_risk_save"]["inputSchema"]["properties"]
    for flag in ("likelihood", "impact"):
        assert props[flag]["type"] == "integer"
        assert props[flag]["enum"] == [1, 2, 3, 4, 5], props[flag]
