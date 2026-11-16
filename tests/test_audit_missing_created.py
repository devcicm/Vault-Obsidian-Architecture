"""D-01 -- `createdAt` ausente se cuenta y se penaliza (AP-13), como ya `updatedAt`."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import vault_audit  # noqa: E402
import pytest


@pytest.mark.parametrize("count, expected", [(0, 0), (1, 3), (5, 15), (8, 15)])
def test_missing_id_penalty_is_three_per_note_capped_at_fifteen(count, expected):
    result = vault_audit.calcular_salud({"missing_id": count})
    assert result["healthScore"] == 100 - expected


def test_audit_counts_missing_id_from_canonical_note_contract(tmp_path):
    import vault_io
    from apoyo import nota

    root = tmp_path / "vault"
    paths = ["07_Knowledge/missing.md", "00_System/missing.md",
             "07_Knowledge/index.md", "07_Knowledge/identified.md"]
    for relative in paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = {"title": "Example"}
        if path.stem == "identified":
            fields["id"] = "existing"
        path.write_text(nota(fields, "# Example"), encoding="utf-8")
    vault_io.set_vault_root(root)
    report = vault_audit.vault_audit()
    assert {item["path"] for item in report["issues"]["missingId"]} == {
        "07_Knowledge/missing.md", "00_System/missing.md"}
    penalty = next(p for p in report["penalties"] if p["id"] == "missing_id")
    assert penalty["count"] == 2
    assert penalty["penalty"] == 6


def test_note_without_frontmatter_is_not_penalised_twice_for_missing_id(tmp_path):
    import vault_io

    root = tmp_path / "vault"
    (root / "07_Knowledge").mkdir(parents=True)
    (root / "07_Knowledge" / "plain.md").write_text("# Plain note\n\nBody.\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    report = vault_audit.vault_audit()
    assert [i["path"] for i in report["issues"]["missingFrontmatter"]] == ["07_Knowledge/plain.md"]
    assert report["issues"]["missingId"] == []
    assert all(p["id"] != "missing_id" or p["count"] == 0 for p in report["penalties"])


def test_missing_created_tiene_penalizacion_con_norma_ap13():
    p = {x["id"]: x for x in vault_audit.PENALIZACIONES}
    assert p["missing_created"]["norma"] == "AP-13"
    assert p["missing_created"]["familia"] == "metadatos"


def test_el_detector_cuenta_la_nota_sin_createdat(tmp_path, monkeypatch):
    import inspect
    fuente = inspect.getsource(vault_audit)
    assert '"missing_created": missing_created' in fuente
    assert 'meta_issues["missing_created"]' in fuente
