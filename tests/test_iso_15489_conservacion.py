"""ISO 15489: retention schedule per document class and the AP-77 work list.

- The schedule lives in `vault_registry` next to the document class of each
  section; no disposition destroys a record (no-derogation).
- `vault_drift_detect --mode conservacion` lists the records whose retention
  ran out with their disposition pending, with the norms' own arithmetic,
  and never deletes or moves anything.
"""

import inspect
from datetime import date

import pytest

from apoyo import correr_en_proceso, escribir_nota

import vault_io
import vault_registry


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "03_Decisions", "04_Sessions", "05_Patterns",
                    "16_AI_Governance", "20_Quarantine"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _nota(raiz, rel, **fm):
    escribir_nota(raiz, rel, {"title": rel.rsplit("/", 1)[-1], **fm}, "Texto del registro.\n")


# ── Registry ────────────────────────────────────────────────────────────────

def test_every_document_class_and_section_has_a_schedule():
    assert set(vault_registry.CONSERVACION_POR_CLASE) == set(vault_registry.DOCUMENTACION_CLASES)
    assert set(vault_registry.CONSERVACION_POR_SECCION) <= set(vault_registry.SECTION_DOCUMENTACION)
    for seccion in vault_registry.SECTION_DOCUMENTACION:
        regla = vault_registry.conservacion_de(seccion)
        assert regla["disposicion"] in vault_registry.DISPOSICIONES, seccion
        plazo = regla["plazo_dias"]
        assert plazo == vault_registry.PLAZO_PERMANENTE or (isinstance(plazo, int) and plazo > 0)
    assert vault_registry.conservacion_de("55_Propia") is None


def test_no_disposition_destroys_a_record():
    """S6 / no-derogation: the product's dispositions keep the record."""
    assert set(vault_registry.DISPOSICIONES) == {"conservar", "revisar", "archivar"}


def test_a_section_override_wins_over_its_class():
    regla = vault_registry.conservacion_de("20_Quarantine")
    assert regla == {"clase": "registro", "plazo_dias": 90, "disposicion": "revisar",
                     "origen": "seccion"}
    assert vault_registry.conservacion_de("04_Sessions")["origen"] == "clase"


# ── Work list ───────────────────────────────────────────────────────────────

def test_conservacion_lists_records_past_their_retention(vault):
    import vault_drift_detect

    viejo = "2022-01-01T00:00:00Z"
    _nota(vault, "04_Sessions/vieja.md", type="session", createdAt=viejo, updatedAt=viejo)
    _nota(vault, "04_Sessions/archivada.md", type="session", status="archived",
          createdAt=viejo, updatedAt=viejo)
    _nota(vault, "04_Sessions/reciente.md", type="session", createdAt="2026-10-01T00:00:00Z")
    _nota(vault, "05_Patterns/revisada.md", type="pattern", createdAt=viejo,
          revisado_en="2026-10-01")
    _nota(vault, "05_Patterns/sin-revisar.md", type="pattern", createdAt=viejo,
          updatedAt="2023-06-01T10:00:00Z", responsable="ana")
    _nota(vault, "03_Decisions/adr-001-vieja.md", type="adr", createdAt=viejo)
    _nota(vault, "16_AI_Governance/decision.md", type="ai_decision", createdAt=viejo)
    _nota(vault, "20_Quarantine/retenida.md", type="quarantine", createdAt="2026-07-01T00:00:00Z")
    _nota(vault, "04_Sessions/futura.md", type="session", updatedAt="2027-01-01T00:00:00Z")
    _nota(vault, "04_Sessions/sin-fecha.md", type="session")

    res = vault_drift_detect.vault_drift_conservacion(hoy=date(2026, 11, 18))

    assert res["ok"] is True and res["mode"] == "conservacion" and res["norm"] == "AP-77"
    pendientes = {p["path"]: p for p in res["pendientes"]}
    assert set(pendientes) == {"04_Sessions/vieja.md", "05_Patterns/sin-revisar.md",
                               "20_Quarantine/retenida.md"}
    assert pendientes["04_Sessions/vieja.md"]["disposicion"] == "archivar"
    assert pendientes["04_Sessions/vieja.md"]["vence_en"] == "2024-12-31"  # 1095 days, 2024 is leap
    sin_revisar = pendientes["05_Patterns/sin-revisar.md"]
    assert (sin_revisar["disposicion"], sin_revisar["campo"], sin_revisar["ultima_actividad"],
            sin_revisar["responsable"]) == ("revisar", "updatedAt", "2023-06-01", "ana")
    assert pendientes["20_Quarantine/retenida.md"]["plazo_dias"] == 90
    assert res["pendientes_total"] == 3
    assert res["dispuestos"] == 1
    assert res["conservados"] == 2
    assert res["sin_fecha"] == 1
    assert [i["path"] for i in res["ilegibles"]] == ["04_Sessions/futura.md"]
    assert "updatedAt" in res["ilegibles"][0]["problema"]
    assert res["calendario"]["04_Sessions"]["disposicion"] == "archivar"


def test_conservacion_never_deletes_or_moves_a_record(tmp_path):
    from vault_base import copiar_vault

    raiz = copiar_vault(tmp_path / "vault", "demo")
    _nota(raiz, "04_Sessions/vieja.md", type="session", project="demo",
          createdAt="2020-01-01T00:00:00Z")
    _nota(raiz, "04_Sessions/ajena.md", type="session", project="otro",
          createdAt="2020-01-01T00:00:00Z")
    antes = {p.relative_to(raiz).as_posix(): p.read_bytes()
             for p in raiz.rglob("*.md") if not p.relative_to(raiz).parts[0].startswith("00_")}

    corrida = correr_en_proceso("vault_drift_detect", "--project", "demo", "--mode",
                                "conservacion", vault=raiz)

    assert corrida.codigo == 0, corrida.stdout
    assert [p["path"] for p in corrida.envelope["pendientes"]] == ["04_Sessions/vieja.md"]
    despues = {p.relative_to(raiz).as_posix(): p.read_bytes()
               for p in raiz.rglob("*.md") if not p.relative_to(raiz).parts[0].startswith("00_")}
    assert despues == antes


def test_conservacion_still_requires_project_like_every_mode(vault):
    """Previous behavior (AP-63): `--project` is required in every mode."""
    corrida = correr_en_proceso("vault_drift_detect", "--mode", "conservacion", vault=vault)

    assert corrida.codigo == 2 and corrida.envelope["error_code"] == "INVALID_ARGS"


def test_conservacion_uses_the_norms_arithmetic_not_a_copy():
    """AP-57: one owner for the expiry arithmetic."""
    import vault_drift_detect

    fuente = inspect.getsource(vault_drift_detect.vault_drift_conservacion)
    assert "estado_de_revision" in fuente and "timedelta" not in fuente


def test_estado_de_revision_names_the_field_it_was_given():
    from vault_norms_catalog import estado_de_revision

    # Previous behavior: without `campo` the message still names `revisado_en`.
    assert "`revisado_en`" in estado_de_revision("2027-01-01", 10, date(2026, 1, 1))["problema"]
    assert "`updatedAt`" in estado_de_revision("2027-01-01", 10, date(2026, 1, 1),
                                               campo="updatedAt")["problema"]


def test_ap77_is_the_audit_norm_of_the_work_list():
    from vault_norms_catalog import norma_por_codigo

    ap77 = norma_por_codigo("AP-77")
    assert ap77["enforcement"] == "audit"
    assert ap77["tools_detecting"] == ["vault_drift_detect"]
    assert "AP-76" in ap77["distinguido_de"]
    assert "AP-77" in norma_por_codigo("AP-76")["distinguido_de"]
