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
    "vault_graph_fix": "_create_stub",
    "vault_tags": "_generate_tag_index_md",
    "vault_section_index": "_ensure_hub_notes",
    "vault_security_scan": "save_findings_to_vault",
    "vault_write": "generate_frontmatter",
    "vault_ingest": "_build_note",
    "vault_onboard": "_make_frontmatter",
    "vault_preferences": "vault_preferences_set",
    "vault_fundamentals": ("export_doc", "export_framework"),
    "vault_log_error": "vault_log_error",
    "vault_migrate_docs": ("process_file_staging", "vault_migrate_docs"),
    # Editores: reescriben un bloque existente por `Frontmatter.editar`.
    "vault_merge": "_tag_frontmatter",
    # Fuera de `scripts/`: la clave es la ruta del módulo sin `.py`.
    "vault/ciclo_de_vida/producto": "_write_seed",
}


def _fuente(modulo: str) -> Path:
    if "/" in modulo:
        return ROOT / f"{modulo}.py"
    return ROOT / "scripts" / f"{modulo}.py"


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


# Un módulo con más de un escritor los declara en una tupla.
_PARES = sorted(
    (m, f) for m, fs in MIGRADOS.items()
    for f in (fs if isinstance(fs, tuple) else (fs,))
)


@pytest.mark.parametrize("modulo,funcion", _PARES)
def test_ap46_el_escritor_no_monta_el_bloque_a_mano(modulo, funcion):
    arbol = ast.parse(_fuente(modulo).read_text(encoding="utf-8"))
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


FECHA = "2026-10-02"


def test_ap46_el_stub_de_graph_fix_conserva_un_destino_hostil(vault):
    """El destino sale de un wikilink ajeno: ni `#` ni una fecha lo cambian."""
    import vault_graph_fix

    for destino in (HOSTIL.replace('"', "").replace(":", ""), FECHA):
        r = vault_graph_fix._create_stub(vault, destino, ["a.md"], {"category": "concept"})
        assert r["created"], r
        [stub] = [n for n in vault.rglob(f"{destino}.md")]
        fm = _frontmatter(stub)
        assert fm["title"] == destino and fm["referenced_by_count"] == 1
        assert fm["tags"] == ["stub", "graph-fix", "needs-review"]


def test_ap46_el_indice_de_tags_y_los_hubs_nacen_legibles(vault):
    import vault_section_index
    import vault_tags

    texto = vault_tags._generate_tag_index_md({"x": ["a.md"]}, [])
    bloque, _ = separar_frontmatter(texto)
    fm = yaml.safe_load(bloque)
    assert fm["title"] == "Tag Index" and fm["type"] == "index"

    vault_section_index._ensure_hub_notes()
    hub = _frontmatter(vault_section_index._hub_note())
    comandos = _frontmatter(vault_section_index._commands_note())
    assert hub["tags"] == ["nav", "hub"] and hub["norm_refs"] == ["CN-01"]
    assert comandos["id"] == "vault-commands" and comandos["tags"] == ["nav", "commands"]


def test_ap46_security_scan_conserva_proyecto_y_categoria(vault):
    import vault_security_scan

    hallazgo = {
        "ruleId": "SEC-1", "category": "a: b #c", "severity": "critical",
        "owasp": "A01", "cwe": "CWE-79", "file": "x.py", "line": 1,
        "snippet": "x", "mitigation": "m",
    }
    for proyecto in (HOSTIL, FECHA):
        rutas = vault_security_scan.save_findings_to_vault([hallazgo], proyecto)
        assert rutas
        for ruta in rutas:
            fm = _frontmatter(Path(ruta) if Path(ruta).is_absolute() else vault / ruta)
            assert fm["project"] == proyecto
            if "ruleId" in fm:
                assert fm["category"] == "a: b #c" and fm["ruleId"] == "SEC-1"


def test_ap46_la_semilla_de_producto_nace_con_un_hub_legible(tmp_path):
    from vault.ciclo_de_vida import producto

    r = producto.inicializar_runtime(tmp_path / "rt")
    assert r["ok"], r
    fm = _frontmatter(tmp_path / "rt" / "00_System" / "vault-hub.md")
    assert fm["id"] == "vault-hub" and fm["tags"] == ["nav", "hub"]
    assert fm["createdAt"] == fm["updatedAt"]


def test_ap46_vault_write_conserva_texto_y_escribe_legible():
    """El escritor central: lo que entra como texto sale como texto, y una
    etiqueta acentuada se escribe legible en vez de escapada por `json.dumps`
    con su `ensure_ascii` por defecto."""
    import vault_write

    bloque = vault_write.generate_frontmatter(
        HOSTIL, tags=["Ñandú"], norm_refs=["AP-46"],
        meta={"owner": "#infra", "v": "1.0", "fecha": FECHA, "n": 3, "lista": ["é"]},
    )
    fm = yaml.safe_load(separar_frontmatter(bloque + "\n")[0])
    assert fm["title"] == HOSTIL and fm["tags"] == ["Ñandú"]
    assert fm["owner"] == "#infra" and fm["v"] == "1.0" and fm["fecha"] == FECHA
    assert fm["n"] == 3 and fm["lista"] == ["é"] and fm["norm_refs"] == ["AP-46"]
    assert "Ñandú" in bloque


def test_ap46_ingest_conserva_texto_e_instantes_citados():
    """`createdAt` de una nota ingerida siempre salió citado —el lector recibe
    `str`— y el dueño lo mantiene con `texto=True`."""
    import vault_ingest

    nota = vault_ingest._build_note(
        {"title": HOSTIL, "body": "Cuerpo con suficiente texto para la nota."},
        {"tags": [], "wikilinks": []},
        "07_Knowledge", "", FECHA, "inline", "a: b", [],
    )
    fm = yaml.safe_load(separar_frontmatter(nota["content"])[0])
    assert fm["title"] == HOSTIL and fm["source"] == FECHA and fm["agent"] == "a: b"
    assert isinstance(fm["createdAt"], str) and fm["tags"] == ["ingested", "inline"]


def test_ap46_onboard_no_deja_un_extra_crudo():
    """AP-56: un `str` de `extra` salía tal cual tras `k: `, y `#x` se leía
    como comentario: el campo desaparecía con el bloque parseando limpio."""
    import vault_onboard

    bloque = vault_onboard._make_frontmatter(
        HOSTIL, "07_Knowledge", ["Ñandú"],
        {"owner": "#infra", "nota": "a: b", "fecha": FECHA, "n": 2}, "",
    )
    fm = yaml.safe_load(separar_frontmatter(bloque + "\n")[0])
    assert fm["title"] == HOSTIL and fm["tags"] == ["Ñandú"]
    assert fm["owner"] == "#infra" and fm["nota"] == "a: b"
    assert fm["fecha"] == FECHA and fm["n"] == 2 and fm["status"] == "stub"


def test_ap46_preferences_set_conserva_texto_y_createdAt(vault):
    import vault_preferences

    r = vault_preferences.vault_preferences_set(
        "style", HOSTIL, "nunca: usar #tabs", scope="a: b", agent="bot")
    assert r["ok"], r
    [nota] = [n for n in vault.rglob("*.md") if _frontmatter_o_nada(n).get("type") == "preference"]
    fm = _frontmatter(nota)
    assert fm["title"] == HOSTIL and fm["statement"] == "nunca: usar #tabs"
    assert fm["scope"] == "a: b" and isinstance(fm["createdAt"], str)
    creado = fm["createdAt"]
    assert vault_preferences.vault_preferences_set("style", HOSTIL, "otra", agent="bot")["ok"]
    assert _frontmatter(nota)["createdAt"] == creado


def test_ap46_los_documentos_de_fundamentals_nacen_legibles(vault):
    import vault_fundamentals

    vault_fundamentals.export_doc()
    vault_fundamentals.export_framework()
    doc = _frontmatter(vault / "00_System" / "data-fundamentals.md")
    marco = _frontmatter(vault / "00_System" / "data-framework.md")
    assert doc["id"] == "data-fundamentals" and doc["evergreen"] is True
    assert marco["id"] == "data-framework" and marco["cia_sensitivity"] == "public"


def test_ap46_log_error_conserva_titulo_y_proyecto_y_omite_lo_vacio(vault):
    import vault_log_error

    r = vault_log_error.vault_log_error(
        "vulnerability", HOSTIL, "desc", project=FECHA, owasp_category="A01: #x")
    assert r["ok"], r
    fm = _frontmatter(vault / r["path"])
    assert fm["title"] == HOSTIL and fm["project"] == FECHA
    assert fm["owasp_category"] == "A01: #x" and "cwe_id" not in fm

    r = vault_log_error.vault_log_error("error", "sin proyecto", "desc")
    assert _frontmatter(vault / r["path"])["project"] is None


def test_ap46_migrate_docs_conserva_proyecto_titulo_y_distributedTo(tmp_path):
    import vault_migrate_docs

    origen = tmp_path / f"{FECHA}.md"
    origen.write_text("Texto de un documento heredado.\n", encoding="utf-8")
    r = vault_migrate_docs.process_file_staging(origen, HOSTIL)
    fm = yaml.safe_load(separar_frontmatter(r["content"])[0])
    assert fm["title"] == FECHA and fm["project"] == HOSTIL
    assert fm["tags"] == [HOSTIL, "migrated"] and fm["distributedTo"] == ""
