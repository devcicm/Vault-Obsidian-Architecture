"""ISO/IEC/IEEE 29119 series: parts 1, 2, 4 and 5 next to the existing part 3.

`ISO-29119` keeps its id and its clause (29119-3, test documentation) so the
manifesto row and `tests/test_iso_aplicada.py` stay valid; the other parts
enter the registry as `ISO-29119-1`, `-2`, `-4` and `-5`.

- 29119-1: test levels and test types as a closed vocabulary. `test_type` is
  already the folder vocabulary of `15_Tests/`, so the 29119-1 types are
  written as `test_kinds`, and a note without them is read through its
  folder type (`unit` -> level `component`).
- 29119-4: `vault_test_save --techniques` validated against the design
  techniques (specification-, structure- and experience-based).
- 29119-2: each test process mapped to the tool that records it, or declared.
- 29119-5: keyword-driven testing stays a declared gap.
"""

from pathlib import Path

import yaml

from apoyo import SCRIPTS, correr_tool
from vault_base import copiar_vault
from vault.kernel.normativa import calidad_iso
from vault_fundamentals_catalog import ISO_COVERAGE


def _vault(tmp_path: Path) -> Path:
    return copiar_vault(tmp_path / "vault", "demo")


def _prueba(raiz: Path, titulo: str, test_type: str, *extra: str):
    return correr_tool("vault_test_save", "--project", "demo", "--title", titulo,
                       "--test_type", test_type, "--description", "Caso de prueba documentado.",
                       *extra, vault=raiz)


def _frontmatter(raiz: Path, rel: str) -> dict:
    return yaml.safe_load((raiz / rel).read_text(encoding="utf-8").split("---", 2)[1])


def _ficheros(raiz: Path) -> dict:
    """Every file of the vault except the tool trace, which each run appends to."""
    return {p.relative_to(raiz).as_posix(): p.read_bytes() for p in raiz.rglob("*")
            if p.is_file() and p.name != ".tool-trace.json"}


# ── Registry ─────────────────────────────────────────────────────────────────

def test_29119_4_techniques_cover_the_three_families_and_resolve_aliases():
    categorias = {t["category"] for t in calidad_iso.TEST_TECHNIQUES}
    assert categorias == {"specification_based", "structure_based", "experience_based"}
    canon, desconocidos = calidad_iso.resolve_terms("techniques", [
        "use case", "Boundary value", "decision_table", "branch coverage", "statement coverage",
        "equivalence partitioning", "state transition", "error guessing", "exploratory", "magia"])
    assert canon == ["equivalence_partitioning", "boundary_value_analysis", "decision_table_testing",
                     "state_transition_testing", "scenario_testing", "statement_testing",
                     "branch_testing", "error_guessing", "exploratory_testing"]
    assert desconocidos == ["magia"]


def test_29119_1_levels_and_the_folder_type_reading():
    assert calidad_iso.vocabulary_ids("test_level") == [
        "component", "integration", "system", "system_integration", "acceptance"]
    assert calidad_iso.resolve_terms("test_level", ["unit"]) == (["component"], [])
    # Every folder type of 15_Tests/ has a 29119-1 reading.
    import vault_test_save
    assert set(calidad_iso.LEGACY_TEST_TYPE) == set(vault_test_save.TEST_TYPES)


def test_29119_2_processes_name_living_tools_or_declare_the_gap():
    capas = [p["layer"] for p in calidad_iso.TEST_PROCESSES]
    assert {"organizational", "management", "dynamic"} == set(capas)
    for p in calidad_iso.TEST_PROCESSES:
        for t in p["tools"]:
            assert (SCRIPTS / f"{t}.py").is_file(), (p["id"], t)
        assert p["tools"] or p["outside_product"], p["id"]
    ejecucion = next(p for p in calidad_iso.TEST_PROCESSES if p["id"] == "test_execution")
    assert "vault_test_runner" in ejecucion["tools"]


def test_registry_keeps_iso_29119_as_part_3_and_adds_the_other_parts():
    por_id = {e["id"]: e for e in ISO_COVERAGE}
    assert por_id["ISO-29119"]["norm"] == "ISO/IEC/IEEE 29119-3:2021"
    assert por_id["ISO-29119"]["cobertura"] == "clausula"
    assert {"vault_test_save", "vault_test_runner"} <= set(por_id["ISO-29119"]["tools"])
    for parte in ("ISO-29119-1", "ISO-29119-2", "ISO-29119-4", "ISO-29119-5"):
        assert parte in por_id, parte
        assert por_id[parte]["norm"].startswith(f"ISO/IEC/IEEE 29119-{parte[-1]}:"), parte
    assert por_id["ISO-29119-5"]["cobertura"] == "parcial"
    assert "palabras clave" in por_id["ISO-29119-5"]["hueco"]


# ── vault_test_save ──────────────────────────────────────────────────────────

def test_test_save_writes_level_kinds_and_techniques_in_canonical_form(tmp_path):
    raiz = _vault(tmp_path)
    r = _prueba(raiz, "Limites del importe", "unit", "--test_level", "unit",
                "--test_kinds", "functional,load", "--techniques",
                "equivalence partitioning, boundary value", "--quality_characteristics",
                "functional_suitability.functional_correctness")
    assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
    fm = _frontmatter(raiz, r.envelope["path"])
    assert fm["test_level"] == "component"
    assert fm["test_kinds"] == ["functional", "performance"]
    assert fm["techniques"] == ["equivalence_partitioning", "boundary_value_analysis"]
    assert fm["quality_characteristics"] == ["functional_suitability.functional_correctness"]


def test_test_save_rejects_an_unknown_technique_and_writes_nothing(tmp_path):
    raiz = _vault(tmp_path)
    antes = _ficheros(raiz)
    r = _prueba(raiz, "Limites del importe", "unit", "--techniques", "boundary value,intuicion")
    assert r.codigo == 1
    assert r.envelope["ok"] is False and r.envelope["error_code"] == "INVALID_VALUE"
    assert "intuicion" in r.envelope["message"]
    assert _ficheros(raiz) == antes


def test_test_save_rejects_two_levels(tmp_path):
    raiz = _vault(tmp_path)
    r = _prueba(raiz, "Dos niveles", "unit", "--test_level", "unit,system")
    assert r.codigo == 1 and r.envelope["error_code"] == "INVALID_VALUE"
    assert not (raiz / "15_Tests" / "unit" / "demo-dos-niveles.md").exists()


def test_test_save_without_the_new_fields_keeps_its_previous_frontmatter(tmp_path):
    """Previous behavior: same keys as before the unit, and a re-save is `unchanged`."""
    raiz = _vault(tmp_path)
    r = _prueba(raiz, "Login ok", "unit", "--related_requirement", "REQ-001", "--status", "pass")
    assert r.codigo == 0 and r.envelope["action"] == "created", r.envelope
    fm = _frontmatter(raiz, r.envelope["path"])
    assert set(fm) == {"id", "test_id", "title", "project", "test_type", "type", "status",
                       "test_result", "related_requirement", "createdAt", "updatedAt", "tags",
                       "cia_integrity", "cia_availability", "cia_sensitivity", "agent"}
    again = _prueba(raiz, "Login ok", "unit", "--related_requirement", "REQ-001", "--status", "pass")
    assert again.envelope["action"] == "unchanged"


# ── Report: tests per level, type and technique ──────────────────────────────

def test_iso_quality_counts_tests_per_level_type_and_technique(tmp_path):
    raiz = _vault(tmp_path)
    assert _prueba(raiz, "Unitaria", "unit", "--techniques", "decision table",
                   "--status", "pass").codigo == 0
    assert _prueba(raiz, "Carga", "performance", "--test_level", "system",
                   "--techniques", "error guessing,branch coverage", "--status", "fail").codigo == 0
    assert _prueba(raiz, "Sin tecnica", "e2e").codigo == 0

    inf = correr_tool("vault_quality_check", "--iso-quality", vault=raiz).envelope
    t = inf["testing"]
    assert t["by_level"] == {"component": 1, "integration": 0, "system": 2,
                             "system_integration": 0, "acceptance": 0}
    assert t["without_level"] == []
    assert t["by_type"]["performance"] == 1 and sum(t["by_type"].values()) == 1
    assert t["by_technique"]["decision_table_testing"] == 1
    assert t["by_technique"]["error_guessing"] == 1 and t["by_technique"]["branch_testing"] == 1
    assert t["by_technique_category"] == {"specification_based": 1, "structure_based": 1,
                                          "experience_based": 1}
    assert t["without_technique"] == ["demo/TEST-003"]
    assert t["by_result"] == {"pass": 1, "fail": 1, "not_run": 1}
