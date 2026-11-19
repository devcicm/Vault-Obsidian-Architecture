"""Karpathy "LLM Wiki" on the ingest path: raw layer, touched pages, saved answers.

Source: the "LLM Wiki" talk (three layers raw/wiki/schema; ingest updates
the pages it touches; good answers are saved back as pages; every operation
is logged). Each test drives the public interface (`vault_ingest` and its
CLI) and asserts what lands on disk, not an internal helper.
"""

import json
from pathlib import Path

import yaml

from apoyo import correr_en_proceso, escribir_nota, filas_de_bitacora

TEXTO = "\n".join([
    "# Zarzaparrilla operativa",
    "La zarzaparrilla describe el procedimiento de arranque del clúster.",
    "Incluye los pasos de verificación previos al despliegue del Context Pack.",
    "Y la forma de revertirlo si el arranque falla; el Context Pack lo resume.",
])


def _vault(tmp_path, monkeypatch) -> Path:
    import vault_io

    raiz = tmp_path / "vault"
    raiz.mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    vault_io.set_vault_root(raiz)
    return raiz


def _frontmatter(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


# ── 1. raw source layer ──────────────────────────────────────────────────────

def test_archivar_fuente_guarda_el_original_literal_y_las_notas_lo_citan(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    fuente = tmp_path / "notas-reunion.md"
    fuente.write_text(TEXTO, encoding="utf-8")
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", str(fuente), "file",
                                  commit=True, agent="pytest", archivar_fuente=True)

    assert r["ok"], r
    archivo = r["archived_source"]["path"]
    assert archivo.startswith("10_Migrated/fuentes/") and archivo.endswith(".md"), archivo
    assert r["archived_source"]["written"] is True
    guardado = raiz / archivo
    assert TEXTO in guardado.read_text(encoding="utf-8")
    fm = _frontmatter(guardado)
    assert fm["type"] == "migrated" and fm["status"] == "archived", fm
    enlace = f"[[{archivo[:-3]}]]"
    for escrita in r["written"]:
        assert _frontmatter(raiz / escrita)["source"] == enlace
        assert enlace in (raiz / escrita).read_text(encoding="utf-8")


def test_sin_archivar_fuente_no_se_escribe_nada_en_10_migrated(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  commit=True, agent="pytest")

    assert r["ok"] and r["written"], r
    assert r["archived_source"] is None
    assert not (raiz / "10_Migrated").exists()
    assert _frontmatter(raiz / r["written"][0])["source"] == "--text"


def test_archivar_fuente_en_dry_run_propone_y_no_escribe(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  agent="pytest", archivar_fuente=True)

    assert r["ok"] and r["committed"] is False, r
    assert r["archived_source"]["written"] is False
    assert not (raiz / "10_Migrated").exists()


def test_archivar_fuente_rechaza_un_binario_ap15(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO + "\x00\x01binario", "07_Knowledge", "--text",
                                  "inline", commit=True, agent="pytest",
                                  archivar_fuente=True)

    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r
    assert "AP-15" in r["message"]
    assert not any(raiz.rglob("*.md"))


def test_archivar_fuente_por_la_cli(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    fuente = tmp_path / "fuente.md"
    fuente.write_text(TEXTO, encoding="utf-8")

    corrida = correr_en_proceso("vault_ingest", "--file", fuente, "--section",
                                "07_Knowledge", "--archivar-fuente", "--commit",
                                vault=raiz, agente="pytest")

    env = corrida.envelope
    assert corrida.codigo == 0 and env["archived_source"]["written"], env
    assert (raiz / env["archived_source"]["path"]).is_file()


# ── 2. ingest touches the pages it affects ───────────────────────────────────

def test_ingesta_propone_anexos_a_las_notas_que_ya_existen(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    existente = escribir_nota(raiz, "07_Knowledge/context-pack.md",
                              {"title": "Context Pack", "type": "knowledge"},
                              "# Context Pack\n\nEl paquete de contexto.\n")
    antes = existente.read_bytes()
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  agent="pytest")

    assert r["ok"], r
    afectadas = {a["path"]: a for a in r["affected_pages"]}
    assert "07_Knowledge/context-pack.md" in afectadas, r["affected_pages"]
    propuesta = afectadas["07_Knowledge/context-pack.md"]
    assert propuesta["entity"] == "Context Pack"
    assert "[[" in propuesta["append"]
    assert existente.read_bytes() == antes  # dry-run never touches a page


def test_ingesta_con_commit_aplica_los_anexos_sin_pisar_la_nota(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    existente = escribir_nota(raiz, "07_Knowledge/context-pack.md",
                              {"title": "Context Pack", "type": "knowledge"},
                              "# Context Pack\n\nEl paquete de contexto.\n")
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  commit=True, agent="pytest")

    assert r["ok"] and r["affected_pages_applied"] is True, r
    fila = next(a for a in r["affected_pages"] if a["path"] == "07_Knowledge/context-pack.md")
    assert fila["applied"] is True
    texto = existente.read_text(encoding="utf-8")
    assert "El paquete de contexto." in texto  # appended, never overwritten
    assert "## Menciones" in texto and fila["append"] in texto


def test_ingesta_no_propone_anexo_a_una_entidad_sin_nota(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  agent="pytest")

    assert r["ok"] and r["affected_pages"] == [], r


# ── 3. operation log vocabulary ──────────────────────────────────────────────

def test_la_bitacora_admite_ingested_y_linted(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    import vault_change_log

    assert {"ingested", "linted"} <= set(vault_change_log.VALID_ACTIONS)
    for accion in ("ingested", "linted"):
        r = vault_change_log.vault_change_log_add(accion, "07_Knowledge/x.md",
                                                  f"prueba {accion}", agent="pytest")
        assert r["ok"], r
    filas = filas_de_bitacora(raiz)
    assert [f["action"] for f in filas] == ["ingested", "linted"]


def test_la_bitacora_sigue_rechazando_una_accion_inventada(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    import vault_change_log

    r = vault_change_log.vault_change_log_add("compiled", "a.md", "x", agent="pytest")
    assert r["ok"] is False and r["error_code"] == "INVALID_ACTION", r


# ── 4. save good answers back as pages ───────────────────────────────────────

def _pack(tmp_path, raiz) -> Path:
    for nombre in ("alfa", "beta"):
        escribir_nota(raiz, f"07_Knowledge/{nombre}.md",
                      {"title": nombre.capitalize(), "type": "knowledge"},
                      f"# {nombre}\n\nContenido de {nombre}.\n")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({
        "ok": True, "query": "como arranca el cluster",
        "included": [{"path": "07_Knowledge/alfa.md"}, {"path": "07_Knowledge/beta.md"}],
    }), encoding="utf-8")
    return pack


def test_desde_pack_escribe_un_borrador_que_cita_las_notas_del_paquete(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    pack = _pack(tmp_path, raiz)

    corrida = correr_en_proceso("vault_ingest", "--text", "El cluster arranca en dos fases.",
                                "--section", "07_Knowledge", "--desde-pack", pack,
                                "--commit", vault=raiz, agente="pytest")

    env = corrida.envelope
    assert corrida.codigo == 0 and len(env["written"]) == 1, env
    nota = raiz / env["written"][0]
    fm = _frontmatter(nota)
    assert fm["related"] == ["07_Knowledge/alfa", "07_Knowledge/beta"]
    assert fm["status"] == "draft"
    cuerpo = nota.read_text(encoding="utf-8")
    assert "[[07_Knowledge/alfa]]" in cuerpo and "[[07_Knowledge/beta]]" in cuerpo
    assert "El cluster arranca en dos fases." in cuerpo
    assert fm["title"] == "Síntesis: como arranca el cluster"


def test_desde_pack_rechaza_un_paquete_sin_notas_del_vault(tmp_path, monkeypatch):
    raiz = _vault(tmp_path, monkeypatch)
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"ok": True, "query": "q", "included": [
        {"path": "07_Knowledge/no-existe.md"}]}), encoding="utf-8")

    corrida = correr_en_proceso("vault_ingest", "--text", "respuesta", "--section",
                                "07_Knowledge", "--desde-pack", pack, "--commit",
                                vault=raiz, agente="pytest")

    assert corrida.codigo == 1 and corrida.envelope["error_code"] == "INVALID_INPUT"
    assert not any(raiz.rglob("*.md"))


def test_el_protocolo_de_sesion_guarda_las_respuestas_al_recordar():
    from vault.meta_toolkit.protocolo_de_sesion import PROTOCOLO_DE_SESION

    pasos = PROTOCOLO_DE_SESION["recordar"]["pasos"]
    guardar = [p for p in pasos if p["tool"] == "vault_ingest"]
    assert guardar and "--desde-pack" in guardar[0]["uso"], pasos
