"""AP-47: los artefactos regenerados dicen qué versión del toolkit los escribió.

Cinco generadores escriben `"version"` con un literal congelado en la versión
que introdujo su formato —v27, v29, v32, v37, v39— mientras el estándar va por
`CURRENT_VERSION`. Quien abría `norm-registry.json` leía `v29` y no podía saber
si el fichero venía de un toolkit viejo o del de hoy.

`version` no se toca: es el campo que ya leen los consumidores, y cambiarle el
significado a mitad de camino es romperles el contrato. El dato que faltaba va
al lado, como `generator_version`, y sale del registro en vez de escribirse.

Quedan fuera, a propósito, el contexto MCP y el índice de etiquetas de código:
son estado que se crea una vez y se actualiza, no artefactos que se regeneran
enteros, así que una versión puesta al crearlos envejecería con el fichero.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_io  # noqa: E402
from vault_version import CURRENT_VERSION  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "07_Knowledge"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    try:
        yield tmp_path
    finally:
        vault_io.set_vault_root(anterior)


def _norm_registry(vault):
    import vault_norms

    vault_norms.vault_norms_rebuild()
    return json.loads(vault_norms._norm_registry().read_text(encoding="utf-8"))


def _data_fundamentals(vault):
    import vault_fundamentals

    vault_fundamentals.export_registry()
    return json.loads((vault / "00_System" / "data-fundamentals.json").read_text(encoding="utf-8"))


def _data_framework(vault):
    import vault_fundamentals

    vault_fundamentals.export_framework()
    return json.loads((vault / "00_System" / "data-framework.json").read_text(encoding="utf-8"))


def _tool_manifest(vault):
    import vault_manifest

    return vault_manifest._bootstrap_spec()


def _graph_enriched(vault):
    import vault_graph_merge

    vault_graph_merge.vault_graph_merge()
    return json.loads(vault_graph_merge._enriched_file().read_text(encoding="utf-8"))["metadata"]


@pytest.mark.parametrize("generar", [
    _norm_registry, _data_fundamentals, _data_framework, _tool_manifest, _graph_enriched,
])
def test_ap47_el_artefacto_declara_la_version_que_lo_genero(vault, generar):
    datos = generar(vault)
    assert datos["generator_version"] == CURRENT_VERSION, datos.get("generator_version")
    # El campo que ya leen los consumidores sigue ahí y con su forma.
    assert isinstance(datos["version"], str) and datos["version"].startswith("v")
