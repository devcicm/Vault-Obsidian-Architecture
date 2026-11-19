"""SQuaRE (ISO/IEC 25000): the evaluation process (25040), data quality (25012),
measurement (25023) and the umbrella entry, each with its executor or its gap.

- 25040: the five evaluation steps map to the tools that record them, and
  `vault_quality_check --iso-quality` counts the records of each step.
  Certification by an independent third party stays outside the product.
- 25012: the fifteen data quality characteristics map to the framework
  dimensions that already measure the vault's data; the unmapped ones are
  the declared gap.
- 25023: the measure the toolkit computes is the share of declared
  requirements covered by tests, per characteristic.
"""

from pathlib import Path

from apoyo import SCRIPTS, correr_tool
from vault_base import copiar_vault
from vault.kernel.normativa import calidad_iso
from vault_fundamentals_catalog import FRAMEWORK_REGISTRIES, ISO_COVERAGE


def _vault(tmp_path: Path) -> Path:
    return copiar_vault(tmp_path / "vault", "demo")


def _registros(informe: dict) -> dict:
    return {s["step"]: s["records"] for s in informe["evaluation_25040"]}


def test_25040_steps_are_the_five_of_the_evaluation_process_with_living_tools():
    pasos = [s["id"] for s in calidad_iso.EVALUATION_25040]
    assert pasos == ["establish_evaluation_requirements", "specify_evaluation",
                     "design_evaluation", "execute_evaluation", "conclude_evaluation"]
    for s in calidad_iso.EVALUATION_25040:
        assert s["tools"], s["id"]
        for t in s["tools"]:
            assert (SCRIPTS / f"{t}.py").is_file(), (s["id"], t)
    concluir = calidad_iso.EVALUATION_25040[-1]
    assert "third party" in concluir["outside_product"]


def test_iso_quality_counts_the_records_of_each_evaluation_step(tmp_path):
    raiz = _vault(tmp_path)
    vacio = correr_tool("vault_quality_check", "--iso-quality", vault=raiz).envelope
    assert set(_registros(vacio).values()) == {0}

    r = correr_tool("vault_requirement_save", "--project", "demo", "--title", "Disponibilidad",
                    "--type", "non-functional", "--priority", "must-have",
                    "--description", "El servicio sigue disponible ante la caida de un nodo.",
                    "--quality_characteristics", "reliability.availability", vault=raiz)
    assert r.codigo == 0, r.envelope
    for titulo, estado in (("Caida de nodo", "pass"), ("Caida de red", "not_run")):
        p = correr_tool("vault_test_save", "--project", "demo", "--title", titulo,
                        "--test_type", "integration", "--description", "Simula la caida.",
                        "--related_requirement", "REQ-001", "--status", estado, vault=raiz)
        assert p.codigo == 0, p.envelope

    inf = correr_tool("vault_quality_check", "--iso-quality", vault=raiz).envelope
    assert _registros(inf) == {"establish_evaluation_requirements": 1, "specify_evaluation": 1,
                               "design_evaluation": 2, "execute_evaluation": 1,
                               "conclude_evaluation": 1}


def test_25012_maps_every_data_quality_characteristic_or_declares_the_gap():
    ids = [c["id"] for c in calidad_iso.DATA_QUALITY_25012]
    assert len(ids) == 15 == len(set(ids))
    marco = {e["id"] for registro in FRAMEWORK_REGISTRIES.values() for e in registro}
    for c in calidad_iso.DATA_QUALITY_25012:
        assert c["point_of_view"] in {"inherent", "both", "system_dependent"}, c["id"]
        assert set(c["framework"]) <= marco, c["id"]
    sin_medida = sorted(c["id"] for c in calidad_iso.DATA_QUALITY_25012 if not c["framework"])
    assert sin_medida == ["efficiency", "precision"]


def test_registry_publishes_the_square_entries_with_their_gaps():
    por_id = {e["id"]: e for e in ISO_COVERAGE}
    esperadas = {"ISO-25000", "ISO-25010", "ISO-25012", "ISO-25019", "ISO-25023", "ISO-25040"}
    assert esperadas <= set(por_id)
    assert por_id["ISO-25010"]["norm"] == "ISO/IEC 25010:2023"
    assert por_id["ISO-25019"]["norm"] == "ISO/IEC 25019:2023"
    assert por_id["ISO-25010"]["hueco"] != (
        "Mide la calidad de las notas del vault, no las características del producto "
        "software que documentan.")
    assert {"vault_requirement_save", "vault_test_save"} <= set(por_id["ISO-25010"]["tools"])
    assert "tercero" in por_id["ISO-25040"]["hueco"]
    assert "eficiencia" in por_id["ISO-25012"]["hueco"] and "precisión" in por_id["ISO-25012"]["hueco"]
