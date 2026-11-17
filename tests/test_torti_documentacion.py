"""Torti Code, «documentación útil»: lo que el vídeo pide, llevado a código.

Fuente: `Documents/scrap_torticode_doc` (fase 4 del plan del 2026-11-16).

- Un ADR nace con su plantilla y su número, en `draft` (`vault_write --adr`).
- Una decisión cerrada se sustituye, no se reescribe — cuando el vault lo
  declara en `00_System/reglas.json` (`sustitucion`); sin declararlo, nada
  cambia.
- El adaptador que lee un agente dice dónde viven las decisiones y, si el
  vault lo declara, con qué comando se prueba (no se inventa).
- Un comentario que cita un ADR apunta a uno que existe (AP-72); en un vault,
  el `@vault:` del código puede apuntar a la decisión que lo explica.
- Una nota con `revisado_en` vencido es trabajo pendiente
  (`vault_drift_detect --mode antiguedad`), con la cadencia del dueño.
"""

from datetime import date
from pathlib import Path

import pytest

from apoyo import correr_en_proceso, escribir_nota

import vault_io
import vault_write
from vault_lib import parse_frontmatter
from vault.kernel.contenido import meta_adr, secciones_adr_faltantes


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "03_Decisions", "07_Knowledge", "11_Code", "17_Preferences"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


#: El porqué que escribe una persona: pasa la valla de contenido (AP-11) y
#: tiene las tres secciones que AP-07 exige.
ADR_COMPLETO = (
    "## Contexto\n\nLas notas se pierden cuando dos agentes escriben a la vez sin lock.\n\n"
    "## Decisión\n\nVamos a serializar las escrituras con un lock por nota y timeout.\n\n"
    "## Consecuencias\n\nUna escritura concurrente espera o falla con NOTE_LOCKED explícito.\n"
)


# ── 1. ADR: plantilla, número libre y `draft` ────────────────────────────────

def test_adr_nace_con_el_siguiente_numero_libre_y_en_draft(vault):
    escribir_nota(vault, "03_Decisions/adr-001-previa.md",
                  {"type": "adr", "status": "draft", "title": "previa"}, ADR_COMPLETO)
    escribir_nota(vault, "03_Decisions/adr-007-otra.md",
                  {"type": "adr", "status": "draft", "title": "otra"}, ADR_COMPLETO)

    corrida = correr_en_proceso(
        "vault_write", "--adr", "--folder", "03_Decisions", "--title", "Serializar escrituras",
        "--content", ADR_COMPLETO, "--tags", "arquitectura", "--agent", "pytest", vault=vault)

    env = corrida.envelope
    assert corrida.codigo == 0 and env["ok"], env
    assert env["adr"]["numero"] == "adr-008"
    nota = vault / "03_Decisions" / "adr-008-serializar-escrituras.md"
    assert nota.is_file()
    fm = parse_frontmatter(nota.read_text(encoding="utf-8"))
    assert fm["type"] == meta_adr()["type"]
    assert fm["status"] == "draft"


def test_adr_sin_secciones_obligatorias_se_rechaza_con_la_plantilla(vault):
    corrida = correr_en_proceso(
        "vault_write", "--adr", "--folder", "03_Decisions", "--title", "Sin secciones",
        "--content", "Linea uno con bastante texto real aqui.\nLinea dos con mas texto real.\n"
                     "Linea tres que completa el minimo de palabras.\n",
        "--tags", "arquitectura", "--agent", "pytest", vault=vault)

    env = corrida.envelope
    assert corrida.codigo == 1 and env["ok"] is False
    assert env["error_code"] == "VALIDATION_FAILED"
    assert "## Contexto" in env["recovery"]["hint"] and "## Consecuencias" in env["recovery"]["hint"]
    assert not list((vault / "03_Decisions").glob("adr-*.md"))


def test_adr_no_ignora_un_status_cerrado_en_meta(vault):
    """Quien redacta no aprueba al escribir (AP-64): `--adr` no acepta `accepted`."""
    corrida = correr_en_proceso(
        "vault_write", "--adr", "--folder", "03_Decisions", "--title", "Aprobada sola",
        "--content", ADR_COMPLETO, "--meta", '{"status": "approved"}',
        "--tags", "arquitectura", "--agent", "pytest", vault=vault)

    assert corrida.codigo == 1
    assert corrida.envelope["error_code"] == "CONFLICTING_ARGS"


def test_adr_fuera_de_03_decisions_se_rechaza(vault):
    corrida = correr_en_proceso(
        "vault_write", "--adr", "--folder", "07_Knowledge", "--title", "Fuera",
        "--content", ADR_COMPLETO, "--tags", "x", "--agent", "pytest", vault=vault)

    assert corrida.codigo == 1
    assert corrida.envelope["error_code"] == "INVALID_FOLDER"


def test_el_ejemplo_publicado_de_adr_no_crea_un_adr_vacio_aceptado():
    """El docstring y el epílogo de `vault_write` enseñaban un ADR `accepted`
    sin contenido: la forma que AP-07 y AP-64 condenan."""
    fuente = Path(vault_write.__file__).read_text(encoding="utf-8")
    for linea in fuente.splitlines():
        if "03_Decisions" in linea and "vault_write.py" in linea:
            assert '"accepted"' not in linea and "'accepted'" not in linea, linea
            assert "--adr" in linea, linea


def test_plantilla_del_adr_pasa_ap07():
    from vault.kernel.contenido import plantilla_adr

    assert secciones_adr_faltantes(plantilla_adr()) == []


# ── 2. Decisiones cerradas: se sustituyen (opt-in) ──────────────────────────

def _adr_cerrado(vault, status="approved"):
    return escribir_nota(
        vault, "03_Decisions/cerrada.md",
        {"type": "adr", "status": status, "title": "cerrada", "responsable": "persona",
         "tags": ["arquitectura"]}, ADR_COMPLETO)


def _reescribir_cerrada(cuerpo_extra="\nUna frase nueva que cambia el porqué.\n"):
    return vault_write.vault_write(
        folder="03_Decisions", title="cerrada", tags=["arquitectura"],
        meta={"agent": "pytest"}, content=ADR_COMPLETO + cuerpo_extra)


def test_sin_declarar_sustitucion_una_decision_cerrada_se_edita_como_siempre(vault):
    _adr_cerrado(vault)

    res = _reescribir_cerrada()

    assert res["ok"], res


def test_declarada_la_sustitucion_editar_una_decision_cerrada_es_immutable_note(vault):
    (vault / "00_System" / "reglas.json").write_text(
        '{"sustitucion": ["03_Decisions"]}', encoding="utf-8")
    nota = _adr_cerrado(vault)
    antes = nota.read_bytes()

    res = _reescribir_cerrada()

    assert res["ok"] is False and res["error_code"] == "IMMUTABLE_NOTE", res
    assert "vault_supersede" in res["message"]
    assert nota.read_bytes() == antes


def test_declarada_la_sustitucion_una_decision_abierta_se_sigue_editando(vault):
    (vault / "00_System" / "reglas.json").write_text(
        '{"sustitucion": ["03_Decisions"]}', encoding="utf-8")
    _adr_cerrado(vault, status="draft")

    assert _reescribir_cerrada()["ok"]


def test_declarada_la_sustitucion_anotar_superseded_by_sigue_permitido(vault):
    """`vault_supersede` cambia el frontmatter, no el porqué: es la vía."""
    import vault_supersede

    (vault / "00_System" / "reglas.json").write_text(
        '{"sustitucion": ["03_Decisions"]}', encoding="utf-8")
    nota = _adr_cerrado(vault)
    escribir_nota(vault, "03_Decisions/adr-002-sucesora.md",
                  {"type": "adr", "status": "draft", "title": "sucesora"}, ADR_COMPLETO)

    res = vault_supersede.supersede("03_Decisions/cerrada.md",
                                    "adr-002-sucesora", apply=True)

    assert res["ok"], res
    assert "superseded_by" in nota.read_text(encoding="utf-8")


def test_el_registro_declara_la_sustitucion_como_guard_solo_si_se_opta():
    import vault_registry as reg

    assert reg.enforcement_de_modo("sustitucion", declarado=False) == "recommended"
    assert reg.enforcement_de_modo("sustitucion", declarado=True) == "guard"
    assert reg.enforcement_de_modo("historia", declarado=True) == "guard"
    assert reg.MODOS_DE_VERSION["sustitucion"]["clave_de_politica"] == "sustitucion"


# ── 3. El adaptador dice dónde viven las decisiones y el comando de pruebas ──

def _adaptador(tmp_path) -> str:
    import vault_preferences

    destino = tmp_path / "proyecto"
    destino.mkdir()
    res = vault_preferences.vault_preferences_adapters(str(destino))
    assert res.get("ok"), res
    return (destino / "AGENTS.md").read_text(encoding="utf-8")


def test_el_adaptador_manda_leer_las_decisiones_antes_de_cambiar(vault, tmp_path):
    import vault_preferences
    from vault_registry import SECTION_DOCUMENTACION

    texto = _adaptador(tmp_path)

    assert "## Decisiones" in texto
    assert "Leer `03_Decisions/` antes de cambiar" in texto
    assert SECTION_DOCUMENTACION["03_Decisions"][1] in texto
    assert len(texto.splitlines()) <= vault_preferences.LINEAS_MAXIMAS_ADAPTER


def test_el_adaptador_no_inventa_un_comando_de_pruebas(vault, tmp_path):
    texto = _adaptador(tmp_path)

    assert "## Comando de pruebas" not in texto
    assert "pytest" not in texto


def test_el_adaptador_publica_el_comando_de_pruebas_que_el_vault_declara(vault, tmp_path):
    (vault / "00_System" / "reglas.json").write_text(
        '{"comandos_de_prueba": ["python -m pytest tests/ -q"]}', encoding="utf-8")

    texto = _adaptador(tmp_path)

    assert "## Comando de pruebas" in texto
    assert "`python -m pytest tests/ -q`" in texto


# ── 4. AP-72: un ADR citado existe; `@vault:` puede apuntar a una decisión ──

def test_ap72_una_cita_a_un_adr_inexistente_es_un_problema(tmp_path):
    import vault_doc_sync

    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0001-existe.md").write_text("# ADR-0001\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    rota = "ADR-" + "0042"  # construida: este fichero también se mide
    (tmp_path / "scripts" / "modulo.py").write_text(
        f"# ver ADR-0001\n# ver {rota}\nX = 1\n", encoding="utf-8")

    problemas = vault_doc_sync.adr_citados_sin_fichero(tmp_path, ("scripts",))

    assert [p["kind"] for p in problemas] == ["adr_sin_fichero"]
    assert rota in problemas[0]["detail"] and "AP-72" in problemas[0]["detail"]


def test_ap72_el_repo_no_cita_adr_inexistentes():
    import vault_doc_sync

    assert vault_doc_sync.adr_citados_sin_fichero() == []


def test_ap72_codigo_en_el_catalogo_y_guard():
    import vault_norms_catalog

    norma = vault_norms_catalog.norma_por_codigo("AP-72")
    assert norma and norma["enforcement"] == "guard"
    assert "vault_doc_sync" in norma["tools_enforcing"]


def test_code_sync_no_da_por_huerfano_un_vault_que_apunta_a_una_decision(vault, tmp_path):
    import vault_code_sync

    escribir_nota(vault, "03_Decisions/adr-001-colas.md",
                  {"type": "adr", "status": "draft", "title": "colas"}, ADR_COMPLETO)
    escribir_nota(vault, "11_Code/demo/colas.md",
                  {"type": "module", "title": "colas", "source_file": str(tmp_path / "src" / "colas.py")},
                  "Modulo de colas.\n")
    fuente = tmp_path / "src" / "colas.py"
    fuente.parent.mkdir()
    fuente.write_text("# @vault: 03_Decisions/adr-001-colas  — por qué colas\nX = 1\n",
                      encoding="utf-8")

    res = vault_code_sync.vault_code_sync(project="demo", scan_dir=str(fuente.parent))

    assert res["orphan_vault_refs"] == [], res["orphan_vault_refs"]


def test_code_sync_sigue_dando_por_huerfana_una_decision_que_no_existe(vault, tmp_path):
    import vault_code_sync

    escribir_nota(vault, "11_Code/demo/colas.md",
                  {"type": "module", "title": "colas", "source_file": str(tmp_path / "src" / "colas.py")},
                  "Modulo de colas.\n")
    fuente = tmp_path / "src" / "colas.py"
    fuente.parent.mkdir()
    fuente.write_text("# @vault: 03_Decisions/adr-404-no-esta  — nada\nX = 1\n", encoding="utf-8")

    res = vault_code_sync.vault_code_sync(project="demo", scan_dir=str(fuente.parent))

    assert [o["vault_ref_declared"] for o in res["orphan_vault_refs"]] == [
        "03_Decisions/adr-404-no-esta"]


# ── 5. Revisión por fecha: `vault_drift_detect --mode antiguedad` ───────────

def test_antiguedad_lista_las_notas_con_revision_vencida(vault):
    import vault_drift_detect

    escribir_nota(vault, "07_Knowledge/vieja.md",
                  {"type": "concept", "title": "vieja", "revisado_en": "2025-01-01"}, "x\n")
    escribir_nota(vault, "07_Knowledge/fresca.md",
                  {"type": "concept", "title": "fresca", "revisado_en": "2026-11-01"}, "x\n")
    escribir_nota(vault, "07_Knowledge/propia.md",
                  {"type": "concept", "title": "propia", "revisado_en": "2026-10-01",
                   "cadencia_dias": 10}, "x\n")
    escribir_nota(vault, "07_Knowledge/sin-fecha.md", {"type": "concept", "title": "s"}, "x\n")
    escribir_nota(vault, "07_Knowledge/futura.md",
                  {"type": "concept", "title": "f", "revisado_en": "2027-01-01"}, "x\n")

    res = vault_drift_detect.vault_drift_antiguedad(cadencia_dias=180, hoy=date(2026, 11, 16))

    assert res["ok"] and res["mode"] == "antiguedad"
    vencidas = {v["path"]: v for v in res["vencidas"]}
    assert set(vencidas) == {"07_Knowledge/vieja.md", "07_Knowledge/propia.md"}
    assert vencidas["07_Knowledge/propia.md"]["cadencia_dias"] == 10
    assert res["sin_fecha"] == 1
    assert [p["path"] for p in res["ilegibles"]] == ["07_Knowledge/futura.md"]


def test_antiguedad_usa_la_cadencia_del_dueno_no_una_copia():
    """AP-57: la aritmética de vencimiento es la de las normas."""
    import inspect

    import vault_drift_detect

    fuente = inspect.getsource(vault_drift_detect.vault_drift_antiguedad)
    assert "estado_de_revision" in fuente and "timedelta" not in fuente


def test_antiguedad_por_cli_acota_al_proyecto_sin_exigir_ruta(tmp_path):
    """AP-63: `--project` stays required (published MCP contract); it scopes the notes."""
    from vault_base import copiar_vault

    raiz = copiar_vault(tmp_path / "vault", "demo")
    escribir_nota(raiz, "07_Knowledge/vieja.md", {"type": "concept", "title": "vieja",
                  "project": "demo", "revisado_en": "2020-01-01"}, "x\n")
    escribir_nota(raiz, "07_Knowledge/ajena.md", {"type": "concept", "title": "ajena",
                  "project": "otro", "revisado_en": "2020-01-01"}, "x\n")

    corrida = correr_en_proceso("vault_drift_detect", "--project", "demo", "--mode", "antiguedad",
                                vault=raiz)

    assert corrida.codigo == 0, corrida.stdout
    assert [v["path"] for v in corrida.envelope["vencidas"]] == ["07_Knowledge/vieja.md"]
    sin_proyecto = correr_en_proceso("vault_drift_detect", "--mode", "antiguedad", vault=raiz)
    assert sin_proyecto.codigo == 2 and sin_proyecto.envelope["error_code"] == "INVALID_ARGS"


def test_los_demas_modos_siguen_exigiendo_project(vault):
    """Lo de antes no cambia: `--project` se exige en todos los modos (AP-63)."""
    corrida = correr_en_proceso("vault_drift_detect", "--mode", "report", vault=vault)

    assert corrida.codigo == 2
    assert corrida.envelope["error_code"] == "INVALID_ARGS"
    assert "--project" in corrida.envelope["message"]


# ── 7. AGENTS.md del repo: resumen para agentes y dónde viven las decisiones ─

def test_agents_md_abre_con_el_resumen_para_agentes():
    from apoyo import ROOT

    texto = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    cabeza = "\n".join(texto.splitlines()[:12])
    for pieza in ("python scripts/vault_test_scope.py --changed --correr",
                  "python scripts/vault_gate.py --strict --nivel rapida",
                  "`docs/adr/`", "`vault-sandbox/`"):
        assert pieza in cabeza, pieza
    fuentes = texto.split("## Fuentes únicas de verdad", 1)[1].split("\n## ", 1)[0]
    assert "`docs/adr/NNNN-*.md`" in fuentes and "AP-72" in fuentes


def test_audit_guidance_proposes_the_adr_write_path_not_an_empty_template(tmp_path):
    """The roadmap pointed at `vault_write` with an empty template, which AP-11 rejects."""
    import vault_audit
    import vault_io

    (tmp_path / "07_Knowledge").mkdir()
    nota = tmp_path / "07_Knowledge" / "a.md"
    nota.write_text("---\ntitle: A\n---\n\n# A\n\nTexto.\n", encoding="utf-8")
    previa = vault_io.set_vault_root(tmp_path)
    try:
        acciones = vault_audit._get_roadmap_for_populated_vault([nota])
    finally:
        vault_io.set_vault_root(previa)
    adr = next(a for a in acciones if "03_Decisions" in a["command"])
    assert "--adr" in adr["command"]
    assert "--content @file:" in adr["command"]
    assert "## Contexto" not in adr["command"]
    assert "## Contexto" in adr["template"] or "Contexto" in adr["template"]
