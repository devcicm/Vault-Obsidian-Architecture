"""AP-46: los escritores que montaban su frontmatter a mano pasan por su dueño.

`vault/autoria/frontmatter.py:Frontmatter` decide el escapado una sola vez. Los
sitios de aquí construían la lista `["---", f"title: …", …, "---"]` cada uno con
su criterio, y `vault_env_matrix` citaba el título entre comillas dobles sin
escapar: un proyecto con `"` dejaba la nota sin frontmatter, sin error en
ninguna parte. El criterio de la prueba es el del consumidor (AP-44):
`yaml.safe_load` tiene que devolver exactamente lo que se pasó.
"""

import ast
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402

HOSTIL = 'Ñandú "x": v2 #y'

#: módulo → función que ya no puede montar el bloque a mano.
MIGRADOS = {
    "vault_code_map": "vault_code_map",
    "vault_project_overview": "vault_project_overview",
    "vault_infra_map": "vault_infra_map",
    "vault_env_matrix": "vault_env_matrix",
    "vault_ai_decision": "vault_ai_decision",
    "vault_code_module": "vault_code_module",
    "vault_code_relation": "save_code_map",
}


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "09_Infrastructure", "99_Index"):
        (root / sec).mkdir(parents=True)
    vault_io.set_vault_root(root)
    return root


def _frontmatter(path: Path) -> dict:
    texto = path.read_text(encoding="utf-8")
    bloque, _ = separar_frontmatter(texto)
    datos = yaml.safe_load(bloque)
    assert isinstance(datos, dict), texto[:300]
    return datos


@pytest.mark.parametrize("modulo,funcion", sorted(MIGRADOS.items()))
def test_ap46_el_escritor_no_monta_el_bloque_a_mano(modulo, funcion):
    arbol = ast.parse((ROOT / "scripts" / f"{modulo}.py").read_text(encoding="utf-8"))
    [f] = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == funcion]
    delimitadores = [n for n in ast.walk(f) if isinstance(n, ast.Constant) and n.value == "---"]
    assert delimitadores == [], f"{modulo}.{funcion} vuelve a escribir `---` a mano"


def test_ap46_code_map_y_overview_conservan_el_proyecto_hostil(vault):
    import vault_code_map
    import vault_project_overview

    vault_code_map.vault_code_map(HOSTIL)
    vault_project_overview.vault_project_overview(HOSTIL)
    [mapa] = list(vault.rglob("code-map.md"))
    [overview] = list(vault.rglob("overview.md"))
    assert _frontmatter(mapa)["project"] == HOSTIL
    assert _frontmatter(mapa)["title"] == f"Code Map - {HOSTIL}"
    fm = _frontmatter(overview)
    assert fm["project"] == HOSTIL and fm["status"] == "draft"


def test_ap46_infra_map_omite_lo_vacio_como_antes(vault):
    import json

    import vault_infra_map

    # Sin componentes no escribe nota (y aun así devuelve su `path`), así que
    # se siembra uno: lo que se prueba aquí es el frontmatter.
    indice = vault_infra_map._index_file()
    indice.parent.mkdir(parents=True, exist_ok=True)
    indice.write_text(json.dumps({"components": [
        {"name": "db", "project": HOSTIL, "location": "local", "connections": []}
    ], "locations": {}}), encoding="utf-8")
    vault_infra_map.vault_infra_map(project=HOSTIL)
    [nota] = list(vault.rglob("infra-map.md"))
    fm = _frontmatter(nota)
    assert fm["project"] == HOSTIL and "location" not in fm


def test_ap46_env_matrix_no_rompe_el_yaml_con_comillas_en_el_titulo(vault):
    import vault_env_matrix

    vault_env_matrix.vault_env_matrix(HOSTIL, "dev", runtime="node: 20")
    [nota] = list(vault.rglob("*-dev.md"))
    fm = _frontmatter(nota)
    assert fm["title"].startswith(f"Entorno: {HOSTIL} ")
    assert HOSTIL in fm["tags"] and fm["runtime"] == "node: 20"
    # El tag acentuado se escribe legible, no como `\\u00d1` (json.dumps ascii).
    assert "\\u00d1" not in nota.read_text(encoding="utf-8")


def test_ap46_ai_decision_y_code_module_conservan_valores_hostiles(vault):
    import vault_ai_decision
    import vault_code_module
    import vault_code_relation

    r = vault_ai_decision.vault_ai_decision(
        HOSTIL, f"Elegir {HOSTIL}", vault_ai_decision.DECISION_TYPES[0],
        "desc", "porque", tags=[HOSTIL])
    assert r["ok"], r
    [decision] = [n for n in vault.rglob("*.md") if "decisions" in n.parts and n.name != "index.md"]
    fm = _frontmatter(decision)
    assert fm["title"] == f"Elegir {HOSTIL}" and HOSTIL in fm["tags"]
    assert fm["human_approved"] is False and fm["reversible"] is True

    r = vault_code_module.vault_code_module(HOSTIL, "src/app: main.py", "desc", language="python")
    assert r["ok"], r
    [modulo] = [n for n in vault.rglob("*.md") if _frontmatter_o_nada(n).get("type") == "code-module"]
    fm = _frontmatter(modulo)
    assert fm["file_path"] == "src/app: main.py" and fm["project"] == HOSTIL

    mapa = vault_code_relation.save_code_map(HOSTIL, "graph LR\n a-->b")
    assert _frontmatter(mapa)["project"] == HOSTIL


def _frontmatter_o_nada(path: Path) -> dict:
    bloque, _ = separar_frontmatter(path.read_text(encoding="utf-8"))
    return yaml.safe_load(bloque) or {} if bloque else {}
