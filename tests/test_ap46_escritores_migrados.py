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
    "vault_project_status": "vault_project_status",
    "vault_init": "_create_scaffold_note",
    "vault_quality_dashboard": "_build_dashboard",
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
    # Las dos formas: el delimitador suelto en una lista y la plantilla de
    # cadena que abre con él (`f"""---\ntitle: …`).
    delimitadores = [
        n for n in ast.walk(f)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and (n.value == "---" or n.value.startswith("---\n"))
    ]
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


def test_ap46_project_status_conserva_proyecto_estado_e_id(vault):
    import vault_project_status

    # `:` y `"` no caben en un nombre de carpeta de Windows y el proyecto es
    # la carpeta; `#` y `&` sí, y son los que rompían el YAML crudo.
    proyecto = "Ñandú #1 & beta"
    r = vault_project_status.vault_project_status(proyecto, "en_desarrollo", "resumen")
    assert r["ok"], r
    nota = vault / "01_Projects" / proyecto / "status.md"
    fm = _frontmatter(nota)
    # El guion largo lo normaliza el saneado de atomic_write (`—` → `--`).
    assert fm["project"] == proyecto and fm["title"] == f"{proyecto} -- Status"
    assert fm["tags"] == ["status", proyecto] and fm["project_state"] == "en_desarrollo"
    vault_project_status.vault_project_status(proyecto, "bloqueado", "otro")
    segunda = _frontmatter(nota)
    assert segunda["id"] == fm["id"] and segunda["createdAt"] == fm["createdAt"]


def test_ap46_el_primer_de_init_nace_con_una_sola_hora_y_su_tipo(vault):
    import vault_init
    from vault_registry import SCAFFOLD_TYPE

    seccion = "Ñandú #1 & beta"
    r = vault_init._create_scaffold_note(seccion)
    fm = _frontmatter(vault / r["path"])
    assert fm["title"].startswith(seccion) and fm["id"] == seccion.lower() + "-primer"
    assert fm["scaffold"] is True and fm["type"] == SCAFFOLD_TYPE
    assert fm["createdAt"] == fm["updatedAt"] and fm["status"] == "template"


def _frontmatter_o_nada(path: Path) -> dict:
    bloque, _ = separar_frontmatter(path.read_text(encoding="utf-8"))
    return yaml.safe_load(bloque) or {} if bloque else {}


def test_ap46_cumplirla_no_estrena_cruces_hacia_autoria():
    """El dueño vive en el núcleo: adoptarlo no cruza ninguna frontera.

    Desde `vault/autoria/`, cada escritor de Grafo, Infraestructura o Ciclo
    de vida que dejaba de montar el bloque a mano estrenaba un cruce hacia
    Autoría — seis en una tanda, y `vault_arch --check` en rojo. Autoría
    conserva el nombre como reexportación: misma clase, no una segunda.
    """
    import vault_arch
    from vault.autoria.frontmatter import Frontmatter as reexportada
    from vault.kernel.frontmatter_escritura import Frontmatter

    assert reexportada is Frontmatter
    cruces = [c for c in vault_arch.cruces()
              if c["from"] in MIGRADOS and c["to"] == "vault/autoria"]
    assert cruces == []


def test_ap46_el_dashboard_nace_con_un_frontmatter_que_se_lee(vault):
    import json

    import vault_quality_dashboard as qd

    qd._quality_index().write_text(json.dumps({"overall_dq_score": 0.5}), encoding="utf-8")
    r = qd.vault_quality_dashboard()
    fm = _frontmatter(vault / r["path"])
    assert fm["id"] == "quality-dashboard" and fm["tags"] == ["quality", "dashboard", "qa"]
    assert fm["norm_refs"] == ["ISO 9001:2015 §9.1"] and fm["type"] == "observability"


def test_ap46_un_texto_con_forma_de_fecha_sigue_siendo_texto(vault):
    """`yaml_scalar` cita lo que YAML leería como fecha; `set` a secas no,
    porque un `createdAt` tiene que seguir llegando como instante. Un
    proyecto o un fichero llamado `2026-10-02` es texto: la migración que lo
    escribía con `set` lo devolvía al lector como `datetime.date`."""
    import vault_code_map
    import vault_code_module
    import vault_project_status

    fecha = "2026-10-02"
    vault_code_map.vault_code_map(fecha)
    [mapa] = list(vault.rglob("code-map.md"))
    assert _frontmatter(mapa)["project"] == fecha

    assert vault_code_module.vault_code_module(fecha, fecha, "desc")["ok"]
    [modulo] = [n for n in vault.rglob("*.md") if _frontmatter_o_nada(n).get("type") == "code-module"]
    fm = _frontmatter(modulo)
    assert fm["project"] == fm["file_path"] == fm["title"] == fecha

    vault_project_status.vault_project_status(fecha, "en_desarrollo", "r")
    assert _frontmatter(vault / "01_Projects" / fecha / "status.md")["project"] == fecha


def test_ap46_set_texto_es_yaml_scalar():
    from vault.kernel.frontmatter_escritura import Frontmatter
    from vault.kernel.frontmatter_parsing import yaml_scalar

    for valor in ("2026-10-02", "2026-10-02T00:00:00Z", "", "a: b", "plano"):
        [linea] = Frontmatter().set("k", valor, texto=True).campos()
        assert linea == f"k: {yaml_scalar(valor)}"
