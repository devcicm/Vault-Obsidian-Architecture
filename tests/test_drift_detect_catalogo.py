"""La ficha de `vault_drift_detect` en el catálogo describe a esta tool.

Medido el 2026-10-17 al ejecutar todas las líneas de los ejemplos (banco de
AP-37): el `purpose` —que el MCP publica como descripción, lo que un agente
lee para elegir la tool— decía «drift de configuración entre ambientes», los
params escritos a mano eran `compare` («dev-staging, staging-prod»), el
efecto declarado era solo «Reporta», y el ejemplo pasaba `--path
"01_Projects"`, una sección del vault. La tool compara el código de un
proyecto con un snapshot y cruza los cambios con la documentación del vault;
`--path` es la raíz del código, y `--mode snapshot` escribe.
"""

import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_registry  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402

FICHA = TOOLS_CATALOG["vault_drift_detect"]


def test_la_descripcion_es_la_de_la_tool():
    publicado = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json")
                           .read_text(encoding="utf-8"))["tools"]["vault_drift_detect"]
    for texto in (FICHA["purpose"], publicado["description"]):
        assert "ambientes" not in texto, texto
        assert "document" in texto.lower(), texto


def test_los_params_escritos_a_mano_son_flags_reales():
    assert set(FICHA["params"]) <= {"path", "project", "mode", "extensions"}, FICHA["params"]


def test_el_efecto_declarado_incluye_el_snapshot():
    assert any("snapshot" in e.lower() for e in FICHA["side_effects"]), FICHA["side_effects"]


def test_el_path_del_ejemplo_es_codigo_y_no_una_seccion_del_vault():
    for linea in FICHA["example"].splitlines():
        partes = shlex.split(linea)
        if "--path" in partes:
            cabeza = partes[partes.index("--path") + 1].split("/")[0]
            assert cabeza not in vault_registry.ORDERED_SECTIONS, linea
