"""Part A of the POS stress plan: transcript practices as governance norms.

Source: `odd/tasks/pos-simulation-vault-stress-plan.md` (Part A table and L3).

- AP-73: an archived raw source is never rewritten (guard in the write owner)
  and the audit compares it with the body hash recorded at archive time.
- AP-74: every ingested note can be followed to the `ingested` log row of its
  pass; the audit lists the ones that cannot (read-only).
- AP-75: a closed decision is superseded, not rewritten: guard when the vault
  opts in (`sustitucion`), audit always against the note's `.history/`.
- AP-76: a living note past its review cadence is a work list.
- PAT-8 / PAT-9: the answer compiled into the wiki and the generated agent
  schema, whose line budget is a guard.
- AP-07 / AP-64 hardened to `guard+audit` at the mutation boundary.
- AP-01, AP-04 and AP-08 stay `audit` and say why.

Every test drives a public interface (the tool function, its CLI or the write
owner every writer goes through) and asserts what lands on disk.
"""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from apoyo import escribir_nota, nota

import vault_io

TEXTO = "\n".join([
    "# Pasarela de cobro",
    "La pasarela de cobro rechaza un segundo cargo con la misma referencia.",
    "Los reintentos con tarjeta se deshabilitan cuando la respuesta tarda.",
    "La conciliación diaria cruza el Corte Z con los cargos de la pasarela.",
])

ADR_COMPLETO = (
    "## Contexto\n\nLas notas se pierden cuando dos agentes escriben a la vez sin lock.\n\n"
    "## Decisión\n\nVamos a serializar las escrituras con un lock por nota y timeout.\n\n"
    "## Consecuencias\n\nUna escritura concurrente espera o falla con NOTE_LOCKED explícito.\n"
)

#: Three real lines (AP-11) and no Contexto/Decisión/Consecuencias headings.
ADR_INCOMPLETO = (
    "Las notas se pierden cuando dos agentes escriben a la vez sin lock.\n"
    "Vamos a serializar las escrituras con un lock por nota y timeout.\n"
    "Una escritura concurrente espera o falla con NOTE_LOCKED explícito.\n"
)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "03_Decisions", "07_Knowledge", "10_Migrated"):
        (raiz / seccion).mkdir(parents=True)
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _fm(ruta: Path) -> dict:
    return yaml.safe_load(ruta.read_text(encoding="utf-8").split("---", 2)[1])


def _ingerir(vault, tmp_path, archivar=True):
    import vault_ingest

    fuente = tmp_path / "pasarela.md"
    fuente.write_text(TEXTO, encoding="utf-8")
    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", str(fuente), "file",
                                  commit=True, agent="pytest", archivar_fuente=archivar)
    assert r["ok"] and r["written"], r
    return r


def _auditar():
    import vault_audit

    return vault_audit.vault_audit()


# ── AP-73: archived raw source ───────────────────────────────────────────────

def test_ap73_rewriting_an_archived_source_is_refused_by_the_write_owner(vault, tmp_path):
    r = _ingerir(vault, tmp_path)
    archivo = vault / r["archived_source"]["path"]
    antes = archivo.read_bytes()

    with pytest.raises(vault_io.NotaInmutableError) as exc:
        vault_io.atomic_write_text(archivo, f"{archivo.read_text(encoding='utf-8')}\nEditado.\n")

    assert exc.value.codigo == "IMMUTABLE_NOTE"
    assert "AP-73" in str(exc.value) and "vault_ingest" in str(exc.value)
    assert archivo.read_bytes() == antes


def test_ap73_any_writer_through_the_owner_gets_immutable_note(vault, tmp_path):
    from vault.autoria.append import vault_append

    r = _ingerir(vault, tmp_path)
    rel = r["archived_source"]["path"]
    antes = (vault / rel).read_bytes()

    res = vault_append(rel, "Una línea que nadie debía añadir a la fuente.")

    assert res["ok"] is False and res["error_code"] == "IMMUTABLE_NOTE", res
    assert "AP-73" in res["message"]
    assert (vault / rel).read_bytes() == antes


def test_ap73_an_identical_write_and_a_non_archived_note_are_not_blocked(vault, tmp_path):
    r = _ingerir(vault, tmp_path)
    archivo = vault / r["archived_source"]["path"]
    vault_io.atomic_write_text(archivo, archivo.read_text(encoding="utf-8"))  # no-op

    borrador = escribir_nota(vault, "10_Migrated/fuentes/borrador.md",
                             {"title": "b", "type": "migrated", "status": "draft"}, "x\n")
    vault_io.atomic_write_text(borrador, f"{borrador.read_text(encoding='utf-8')}y\n")
    assert borrador.read_text(encoding="utf-8").endswith("y\n")


def test_ap73_archive_records_the_body_hash_and_the_audit_sees_a_hand_edit(vault, tmp_path):
    r = _ingerir(vault, tmp_path)
    rel = r["archived_source"]["path"]
    archivo = vault / rel
    assert len(_fm(archivo)["sha256_cuerpo"]) == 64

    limpio = _auditar()["archivedSourcesModified"]
    assert limpio["norm"] == "AP-73" and limpio["checked"] == 1 and limpio["modified"] == []

    # Outside the owner (an editor, a script): only the audit can see it.
    archivo.write_text(archivo.read_text(encoding="utf-8").replace("segundo cargo", "tercer cargo"),
                       encoding="utf-8")
    sucio = _auditar()["archivedSourcesModified"]
    assert [m["path"] for m in sucio["modified"]] == [rel]


def test_ap73_a_source_without_body_hash_is_unverifiable_not_intact(vault):
    escribir_nota(vault, "10_Migrated/fuentes/vieja-abcd1234.md",
                  {"title": "Fuente: vieja", "type": "migrated", "status": "archived",
                   "sha256": "0" * 64}, "Texto de una fuente archivada antes de la huella.\n")

    res = _auditar()["archivedSourcesModified"]

    assert res["modified"] == []
    assert [u["path"] for u in res["unverifiable"]] == ["10_Migrated/fuentes/vieja-abcd1234.md"]


# ── AP-74: operation without log row ────────────────────────────────────────

def test_ap74_an_ingest_with_its_row_is_clean_and_without_it_is_listed(vault, tmp_path):
    r = _ingerir(vault, tmp_path, archivar=False)
    pasada = _fm(vault / r["written"][0])["ingest_pass"]
    assert all(_fm(vault / w)["ingest_pass"] == pasada for w in r["written"])

    limpio = _auditar()["ingestsWithoutLog"]
    assert limpio["norm"] == "AP-74" and limpio["missing"] == []
    assert limpio["checked"] == len(r["written"])

    bitacora = vault / "00_System" / ".change-log.json"
    filas = json.loads(bitacora.read_text(encoding="utf-8"))
    bitacora.write_text(json.dumps([f for f in filas if f["action"] != "ingested"]),
                        encoding="utf-8")
    antes = bitacora.read_bytes()

    sucio = _auditar()["ingestsWithoutLog"]
    assert {m["path"] for m in sucio["missing"]} == set(r["written"])
    assert bitacora.read_bytes() == antes  # read-only


def test_ap74_an_ingested_note_without_pass_is_unverifiable(vault):
    escribir_nota(vault, "07_Knowledge/legado.md",
                  {"title": "legado", "type": "ingested", "status": "draft",
                   "tags": ["ingested"]}, "Nota ingerida antes de que existiera la pasada.\n")

    res = _auditar()["ingestsWithoutLog"]

    assert res["missing"] == [] and res["unverifiable"] == 1


# ── AP-75: closed decision rewritten ─────────────────────────────────────────

def _adr_cerrado(vault, nombre="cerrada", **extra):
    return escribir_nota(
        vault, f"03_Decisions/{nombre}.md",
        {"type": "adr", "status": "approved", "title": nombre, "responsable": "persona",
         "tags": ["arquitectura"], **extra}, ADR_COMPLETO)


def test_ap75_the_opt_in_guard_names_the_norm(vault):
    import vault_write

    (vault / "00_System" / "reglas.json").write_text('{"sustitucion": ["03_Decisions"]}',
                                                     encoding="utf-8")
    nota = _adr_cerrado(vault)
    antes = nota.read_bytes()

    res = vault_write.vault_write(folder="03_Decisions", title="cerrada", tags=["arquitectura"],
                                  meta={"agent": "pytest"},
                                  content=f"{ADR_COMPLETO}\nUna frase nueva que cambia el porqué.\n")

    assert res["ok"] is False and res["error_code"] == "IMMUTABLE_NOTE", res
    assert "AP-75" in res["message"] and "vault_supersede" in res["message"]
    assert nota.read_bytes() == antes


def test_ap75_the_audit_sees_a_closed_decision_rewritten_through_its_history(vault):
    import vault_write

    _adr_cerrado(vault)
    _adr_cerrado(vault, "sin-historia")
    res = vault_write.vault_write(folder="03_Decisions", title="cerrada", tags=["arquitectura"],
                                  meta={"agent": "pytest"},
                                  content=f"{ADR_COMPLETO}\nUna frase nueva que cambia el porqué.\n")
    assert res["ok"], res  # without the opt-in the rewrite is allowed...

    aud = _auditar()["closedDecisionsRewritten"]  # ...and the audit still sees it

    assert aud["norm"] == "AP-75"
    assert [x["path"] for x in aud["rewritten"]] == ["03_Decisions/cerrada.md"]
    assert [x["path"] for x in aud["unverifiable"]] == ["03_Decisions/sin-historia.md"]


def test_ap75_a_decision_closed_in_its_last_write_is_not_rewritten(vault):
    import vault_write

    escribir_nota(vault, "03_Decisions/abierta.md",
                  {"type": "adr", "status": "reviewed", "title": "abierta",
                   "tags": ["arquitectura"]}, ADR_COMPLETO)
    res = vault_write.vault_write(folder="03_Decisions", title="abierta", tags=["arquitectura"],
                                  meta={"agent": "pytest", "status": "approved",
                                        "responsable": "persona"},
                                  content=f"{ADR_COMPLETO}\nAjuste antes de aprobarla.\n")
    assert res["ok"], res

    aud = _auditar()["closedDecisionsRewritten"]

    assert aud["rewritten"] == [] and aud["checked"] == 1


# ── AP-76: living note past its review cadence ───────────────────────────────

def test_ap76_the_review_work_list_names_its_norm_and_does_not_fail(vault):
    import vault_drift_detect
    from vault_norms_catalog import norma_por_codigo

    escribir_nota(vault, "07_Knowledge/vieja.md",
                  {"type": "concept", "title": "vieja", "revisado_en": "2025-01-01"}, "x\n")

    res = vault_drift_detect.vault_drift_antiguedad(cadencia_dias=180, hoy=date(2026, 11, 16))

    assert res["ok"] is True and res["norm"] == "AP-76"
    assert [v["path"] for v in res["vencidas"]] == ["07_Knowledge/vieja.md"]
    ap76 = norma_por_codigo("AP-76")
    assert ap76["enforcement"] == "audit" and ap76["tools_detecting"] == ["vault_drift_detect"]


# ── PAT-8: answer compiled into the wiki ─────────────────────────────────────

def test_pat8_a_saved_answer_declares_the_pattern(vault, tmp_path):
    import vault_ingest
    from vault_norms_catalog import norma_por_codigo

    for nombre in ("alfa", "beta"):
        escribir_nota(vault, f"07_Knowledge/{nombre}.md",
                      {"title": nombre, "type": "knowledge"}, f"# {nombre}\n\nContenido.\n")
    pack = {"ok": True, "query": "como se cobra",
            "included": [{"path": "07_Knowledge/alfa.md"}, {"path": "07_Knowledge/beta.md"}]}

    r = vault_ingest.vault_ingest("Se cobra en dos fases y sin reintentos.", "07_Knowledge",
                                  "pack.json", "inline", commit=True, agent="pytest", pack=pack)

    assert r["ok"] and r["pattern"] == "PAT-8", r
    assert _fm(vault / r["written"][0])["status"] == "draft"
    pat8 = norma_por_codigo("PAT-8")
    assert pat8["enforcement"] == "recommended" and pat8["tools_del_patron"] == ["vault_ingest"]


def test_pat8_a_plain_ingest_does_not_claim_the_pattern(vault, tmp_path):
    r = _ingerir(vault, tmp_path, archivar=False)

    assert "pattern" not in r


# ── PAT-9: generated agent schema with a line budget ─────────────────────────

def test_pat9_the_adapter_refuses_to_exceed_its_line_budget(vault, tmp_path, monkeypatch):
    import vault_preferences

    destino = tmp_path / "proyecto"
    destino.mkdir()
    monkeypatch.setattr(vault_preferences, "LINEAS_MAXIMAS_ADAPTER", 10)

    res = vault_preferences.vault_preferences_adapters(str(destino))

    assert res["ok"] is False and res["error_code"] == "VALIDATION_FAILED", res
    assert "PAT-9" in res["message"]
    assert list(destino.iterdir()) == []


def test_pat9_within_budget_the_adapter_is_written(vault, tmp_path):
    import vault_preferences
    from vault_norms_catalog import norma_por_codigo

    destino = tmp_path / "proyecto"
    destino.mkdir()

    res = vault_preferences.vault_preferences_adapters(str(destino))

    assert res["ok"], res
    texto = (destino / "AGENTS.md").read_text(encoding="utf-8")
    assert len(texto.splitlines()) <= vault_preferences.LINEAS_MAXIMAS_ADAPTER
    assert norma_por_codigo("PAT-9")["tools_del_patron"] == ["vault_preferences"]


# ── AP-07 hardened: a closed ADR without its sections is refused ─────────────

def _escribir_adr(titulo, contenido, **meta):
    import vault_write

    return vault_write.vault_write(folder="03_Decisions", title=titulo, tags=["arquitectura"],
                                   meta={"type": "adr", "agent": "pytest", **meta},
                                   content=contenido)


def test_ap07_closing_an_adr_without_sections_is_refused_with_the_template(vault):
    from vault.kernel.contenido import plantilla_adr

    res = _escribir_adr("incompleta", ADR_INCOMPLETO, status="approved", responsable="persona")

    assert res["ok"] is False and res["error_code"] == "VALIDATION_FAILED", res
    assert "AP-07" in res["message"]
    assert plantilla_adr().strip() in res["recovery"]["hint"]
    assert not (vault / "03_Decisions" / "incompleta.md").exists()


def test_ap07_the_owner_refuses_it_for_every_writer(vault):
    destino = vault / "03_Decisions" / "directa.md"
    texto = nota({"title": "directa", "type": "adr", "status": "approved",
                  "responsable": "persona"}, ADR_INCOMPLETO)

    with pytest.raises(vault_io.DecisionCerradaInvalidaError) as exc:
        vault_io.atomic_write_text(destino, texto)

    assert exc.value.codigo == "VALIDATION_FAILED" and exc.value.norma == "AP-07"
    assert not destino.exists()


def test_ap07_drafts_and_non_adr_notes_are_unaffected(vault):
    assert _escribir_adr("borrador", ADR_INCOMPLETO, status="draft")["ok"]
    res = _escribir_adr("guia-de-uso", ADR_INCOMPLETO, type="guide", status="approved")
    assert res["ok"], res


def test_ap07_an_existing_incomplete_adr_is_untouched_until_its_body_is_rewritten(vault):
    import vault_supersede

    vieja = escribir_nota(vault, "03_Decisions/vieja.md",
                          {"type": "adr", "status": "approved", "title": "vieja",
                           "responsable": "persona", "tags": ["arquitectura"]}, ADR_INCOMPLETO)
    escribir_nota(vault, "03_Decisions/adr-002-sucesora.md",
                  {"type": "adr", "status": "draft", "title": "sucesora"}, ADR_COMPLETO)

    # Frontmatter-only change (the supersede link) is not a rewrite of the why.
    assert vault_supersede.supersede("03_Decisions/vieja.md", "adr-002-sucesora", apply=True)["ok"]
    assert "superseded_by" in vieja.read_text(encoding="utf-8")

    res = _escribir_adr("vieja", f"{ADR_INCOMPLETO}Otra línea que cambia el cuerpo.\n",
                        responsable="persona")
    assert res["ok"] is False and res["error_code"] == "VALIDATION_FAILED", res


# ── AP-64 hardened: closing an ADR without responsable is refused ────────────

def test_ap64_closing_an_adr_without_responsable_is_refused(vault):
    res = _escribir_adr("sin-dueno", ADR_COMPLETO, status="approved")

    assert res["ok"] is False and res["error_code"] == "VALIDATION_FAILED", res
    assert "AP-64" in res["message"] and "responsable" in res["recovery"]["hint"]
    assert not (vault / "03_Decisions" / "sin-dueno.md").exists()


def test_ap64_the_transition_into_closed_is_refused_and_a_draft_is_not(vault):
    assert _escribir_adr("propuesta", ADR_COMPLETO, status="draft")["ok"]
    escribir_nota(vault, "03_Decisions/revisada.md",
                  {"type": "adr", "status": "reviewed", "title": "revisada",
                   "tags": ["arquitectura"]}, ADR_COMPLETO)

    res = _escribir_adr("revisada", ADR_COMPLETO, status="approved")
    assert res["ok"] is False and "AP-64" in res["message"], res

    firmada = _escribir_adr("revisada", ADR_COMPLETO, status="approved", responsable="persona")
    assert firmada["ok"], firmada


def test_ap64_the_agent_signing_its_own_decision_is_refused(vault):
    res = _escribir_adr("autofirmada", ADR_COMPLETO, status="approved", responsable="pytest")

    assert res["ok"] is False and "AP-64" in res["message"], res


def test_ap64_rewriting_a_closed_adr_keeps_its_responsable(vault):
    """vault_write dropped `responsable` on every rewrite; with the guard that
    would turn any edit of a closed decision into an AP-64 refusal."""
    import vault_write

    nota = _adr_cerrado(vault)

    res = vault_write.vault_write(folder="03_Decisions", title="cerrada", tags=["arquitectura"],
                                  meta={"agent": "pytest"},
                                  content=f"{ADR_COMPLETO}\nUna frase más.\n")

    assert res["ok"], res
    assert _fm(nota)["responsable"] == "persona"


def test_ap07_and_ap64_are_guard_plus_audit_in_their_packages():
    from vault_norms_catalog import norma_por_codigo

    for code in ("AP-07", "AP-64"):
        norma = norma_por_codigo(code)
        assert norma["enforcement"] == "guard+audit", code
        assert "vault_io" in norma["tools_enforcing"] and norma["tools_detecting"] == ["vault_norms"]


# ── AP-01, AP-04, AP-08 stay audit, and say why ──────────────────────────────

def test_ap01_ap04_ap08_declare_why_they_are_not_decidable_at_write_time():
    from vault_norms_catalog import norma_por_codigo

    raiz = Path(__file__).resolve().parents[1] / "normas"
    for code in ("AP-01", "AP-04", "AP-08"):
        assert norma_por_codigo(code)["enforcement"] == "audit", code
        porque = (raiz / code / "porque.md").read_text(encoding="utf-8")
        seccion = porque.split("## Por qué no es un guard", 1)
        assert len(seccion) == 2 and len(seccion[1].strip()) > 80, code


# ── SDD: declared methodology gaps ───────────────────────────────────────────

def test_sdd_declares_the_diataxis_mix_and_keeps_one_comment_gap():
    import vault_sdd_init

    huecos = vault_sdd_init.HUECOS_DE_METODOLOGIA
    diataxis = [h for h in huecos.values() if "Diátaxis" in h["pide"]]
    assert len(diataxis) == 1 and diataxis[0]["cobertura_descubierta"].strip()
    comentarios = [h for h in huecos.values() if "porqué" in h["pide"]]
    assert len(comentarios) == 1
    tabla = vault_sdd_init._huecos_de_metodologia()
    assert diataxis[0]["pide"] in tabla
