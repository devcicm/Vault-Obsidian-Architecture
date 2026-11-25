"""ISO/IEC 25010:2023 and 25019:2023: requirements and tests declare the quality they specify.

Before this unit the ISO-25010 registry entry measured only the quality of the
vault's own notes. Requirements (`vault_requirement_save`) and tests
(`vault_test_save`) now declare optional `quality_characteristics` (product
model, 25010:2023) and `quality_in_use` (25019:2023), validated against
`vault.kernel.normativa.calidad_iso`; `vault_quality_check --iso-quality`
reports, per characteristic, the requirements that declare it and the tests
that cover them. The 2011 names of the user's `isos.txt` are accepted aliases
(owner decision S9). A note that does not declare them is written as before.
"""

from pathlib import Path

import yaml

from apoyo import correr_tool, escribir_nota
from vault_base import copiar_vault
from vault.kernel.normativa import calidad_iso


def _vault(tmp_path: Path) -> Path:
    return copiar_vault(tmp_path / "vault", "demo")


def _frontmatter(raiz: Path, rel: str) -> dict:
    texto = (raiz / rel).read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


def _requisito(raiz: Path, titulo: str, *extra: str):
    return correr_tool("vault_requirement_save", "--project", "demo", "--title", titulo,
                       "--type", "non-functional", "--priority", "must-have",
                       "--description", "Descripcion suficiente del requisito de calidad.",
                       *extra, vault=raiz)


def _prueba(raiz: Path, titulo: str, *extra: str):
    return correr_tool("vault_test_save", "--project", "demo", "--title", titulo,
                       "--test_type", "unit", "--description", "Caso de prueba del requisito.",
                       *extra, vault=raiz)


def _ficheros(raiz: Path) -> dict:
    """Every file of the vault except runtime telemetry (.tool-trace.json, .voice-counter)."""
    return {p.relative_to(raiz).as_posix(): p.read_bytes() for p in raiz.rglob("*")
            if p.is_file() and p.name not in (".tool-trace.json", ".voice-counter")}


# ── The registry ─────────────────────────────────────────────────────────────

def test_product_model_is_the_2023_edition_with_nine_characteristics():
    assert calidad_iso.PRODUCT_QUALITY_EDITION == "ISO/IEC 25010:2023"
    assert calidad_iso.characteristic_ids("product") == [
        "functional_suitability", "performance_efficiency", "compatibility",
        "interaction_capability", "reliability", "security", "maintainability",
        "flexibility", "safety"]
    for modelo in calidad_iso.QUALITY_MODELS:
        subs = [s for e in calidad_iso.QUALITY_MODELS[modelo][0] for s in e["subcharacteristics"]]
        assert len(subs) == len(set(subs)), modelo


def test_quality_in_use_has_the_five_characteristics_of_25019():
    assert calidad_iso.QUALITY_IN_USE_EDITION == "ISO/IEC 25019:2023"
    assert calidad_iso.characteristic_ids("in_use") == [
        "effectiveness", "efficiency", "satisfaction", "freedom_from_risk", "context_coverage"]


def test_2011_names_and_isos_txt_wording_resolve_to_the_2023_model():
    canon, desconocidos = calidad_iso.resolve_quality("product", [
        "usability", "Portabilidad", "Adecuación funcional", "Eficiencia de desempeño",
        "security.confidentiality", "maturity", "usability.learnability", "calidad"])
    assert canon == ["functional_suitability", "performance_efficiency", "interaction_capability",
                     "interaction_capability.learnability", "reliability.faultlessness",
                     "security.confidentiality", "flexibility"]
    assert desconocidos == ["calidad"]
    canon, desconocidos = calidad_iso.resolve_quality("in_use", [
        "Efectividad", "eficiencia", "satisfacción", "libertad de riesgo", "cobertura de contexto"])
    assert canon == calidad_iso.characteristic_ids("in_use") and desconocidos == []
    # A subcharacteristic under the wrong characteristic is not silently moved.
    assert calidad_iso.resolve_quality("product", ["safety.confidentiality"]) == (
        [], ["safety.confidentiality"])


# ── Declaring on requirements ────────────────────────────────────────────────

def test_requirement_declares_characteristics_in_canonical_form(tmp_path):
    raiz = _vault(tmp_path)
    r = _requisito(raiz, "Cifrado en reposo", "--quality_characteristics",
                   "usability, security.confidentiality", "--quality_in_use", "Efectividad")
    assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
    fm = _frontmatter(raiz, r.envelope["path"])
    assert fm["quality_characteristics"] == ["interaction_capability", "security.confidentiality"]
    assert fm["quality_in_use"] == ["effectiveness"]
    assert fm["req_id"] == "REQ-001"


def test_requirement_with_unknown_characteristic_is_rejected_and_writes_nothing(tmp_path):
    raiz = _vault(tmp_path)
    antes = _ficheros(raiz)
    r = _requisito(raiz, "Cifrado en reposo", "--quality_characteristics", "security,velocidad")
    assert r.codigo == 1
    assert r.envelope["ok"] is False and r.envelope["error_code"] == "INVALID_VALUE"
    assert "velocidad" in r.envelope["message"]
    assert _ficheros(raiz) == antes


def test_requirement_without_quality_fields_keeps_its_previous_frontmatter(tmp_path):
    """Previous behavior: same keys as before the unit, and a re-save is `unchanged`."""
    raiz = _vault(tmp_path)
    r = _requisito(raiz, "Login seguro")
    assert r.codigo == 0 and r.envelope["action"] == "created", r.envelope
    fm = _frontmatter(raiz, r.envelope["path"])
    assert "quality_characteristics" not in fm and "quality_in_use" not in fm
    assert set(fm) == {"id", "req_id", "title", "project", "req_type", "priority", "status",
                       "createdAt", "updatedAt", "tags", "cia_integrity", "cia_availability",
                       "cia_sensitivity", "agent"}
    assert _requisito(raiz, "Login seguro").envelope["action"] == "unchanged"


def test_requirement_transition_rule_still_applies_with_quality_fields(tmp_path):
    """5e808b8b: an illegal state move is rejected, quality fields or not."""
    raiz = _vault(tmp_path)
    assert _requisito(raiz, "Login seguro", "--quality_characteristics", "security").codigo == 0
    antes = _ficheros(raiz)
    r = _requisito(raiz, "Login seguro", "--quality_characteristics", "security",
                   "--req-id", "REQ-001", "--status", "verified")
    assert r.codigo == 1 and r.envelope["ok"] is False
    assert r.envelope["error_code"] == "illegal_status_transition", r.envelope
    assert _ficheros(raiz) == antes


# ── The coverage report ──────────────────────────────────────────────────────

def _fila(informe: dict, modelo: str, caracteristica: str) -> dict:
    return next(f for f in informe[modelo] if f["characteristic"] == caracteristica)


def test_iso_quality_reports_requirements_and_covering_tests_per_characteristic(tmp_path):
    raiz = _vault(tmp_path)
    assert _requisito(raiz, "Cifrado", "--quality_characteristics", "security.confidentiality").codigo == 0
    assert _requisito(raiz, "Latencia", "--quality_characteristics", "performance_efficiency",
                      "--quality_in_use", "efficiency").codigo == 0
    assert _requisito(raiz, "Login seguro").codigo == 0
    assert _prueba(raiz, "Cifra los datos", "--related_requirement", "REQ-001",
                   "--status", "pass").codigo == 0
    assert _prueba(raiz, "Modulos acoplados", "--quality_characteristics", "maintainability").codigo == 0
    antes = _ficheros(raiz)

    r = correr_tool("vault_quality_check", "--iso-quality", vault=raiz)
    assert r.codigo == 0
    inf = r.envelope
    assert inf["ok"] is True and inf["view"] == "iso_quality" and inf["read_only"] is True
    assert [f["characteristic"] for f in inf["product_quality"]] == calidad_iso.characteristic_ids("product")
    assert _fila(inf, "product_quality", "security") == {
        "characteristic": "security", "requirements": ["demo/REQ-001"], "tests": ["demo/TEST-001"],
        "uncovered_requirements": [], "coverage": 1.0}
    assert _fila(inf, "product_quality", "performance_efficiency") == {
        "characteristic": "performance_efficiency", "requirements": ["demo/REQ-002"], "tests": [],
        "uncovered_requirements": ["demo/REQ-002"], "coverage": 0.0}
    assert _fila(inf, "product_quality", "maintainability")["tests"] == ["demo/TEST-002"]
    assert _fila(inf, "product_quality", "maintainability")["coverage"] is None
    assert _fila(inf, "product_quality", "safety")["requirements"] == []
    assert _fila(inf, "quality_in_use", "efficiency")["uncovered_requirements"] == ["demo/REQ-002"]
    assert inf["measures"] == {"requirements": 3, "requirements_with_characteristic": 2,
                               "requirements_covered_by_tests": 1,
                               "requirement_coverage_ratio": 0.5, "tests": 2}
    assert inf["invalid_declarations"] == []
    assert _ficheros(raiz) == antes, "the view must not write anything"


def test_iso_quality_lists_hand_written_declarations_outside_the_model(tmp_path):
    raiz = _vault(tmp_path)
    escribir_nota(raiz, "15_Tests/unit/demo-a-mano.md", {
        "id": "a-mano", "test_id": "TEST-009", "title": "A mano", "project": "demo",
        "type": "test", "test_type": "unit", "quality_characteristics": ["security", "rapidez"]},
        "# A mano\n\ncuerpo\n")
    inf = correr_tool("vault_quality_check", "--iso-quality", vault=raiz).envelope
    assert inf["invalid_declarations"] == [{"path": "15_Tests/unit/demo-a-mano.md",
                                            "field": "quality_characteristics",
                                            "values": ["rapidez"]}]
    assert _fila(inf, "product_quality", "security")["tests"] == ["demo/TEST-009"]


def test_quality_check_without_the_view_keeps_its_previous_envelope(tmp_path):
    raiz = _vault(tmp_path)
    r = correr_tool("vault_quality_check", "--check", vault=raiz)
    assert r.codigo == 0 and r.envelope["ok"] is True
    assert "view" not in r.envelope and "product_quality" not in r.envelope
