"""Tests TDD: `vault_audit` explica exactamente qué falta para llegar al 100 % de salud."""

from __future__ import annotations

import vault_audit
import vault_audit_catalog
import vault_io


def test_todas_las_penalizaciones_del_catalogo_tienen_guia_de_remediacion():
    ids_catalogo = {p["id"] for p in vault_audit_catalog.PENALIZACIONES}
    ids_guia = set(vault_audit._GUIA_PENALIZACION)
    faltantes = sorted(ids_catalogo - ids_guia)
    assert not faltantes, f"Penalizaciones sin guia para llegar a 100 %: {faltantes}"


def test_to_reach_100_en_salud_perfecta_reporta_at100_sin_bloqueos():
    salud = vault_audit.calcular_salud({})
    plan = vault_audit._construir_to_reach_100(salud)
    assert plan["at100"] is True
    assert plan["missingHealthScorePoints"] == 0
    assert plan["missingHealthIndexPoints"] == 0
    assert plan["rawPenaltyTotal"] == 0
    assert plan["blockers"] == []
    assert "100/100" in plan["summary"]


def test_to_reach_100_explica_penalizaciones_parciales_y_saturacion_en_cero():
    # Caso 1: rating 95/98 (una sola penalizacion que antes no salia en nextActions)
    salud_95 = vault_audit.calcular_salud({"missing_type": 2, "missing_status": 1})
    plan_95 = vault_audit._construir_to_reach_100(
        salud_95,
        {"missing_type": ["07_Knowledge/a.md", "07_Knowledge/b.md"], "missing_status": ["07_Knowledge/a.md"]},
    )
    assert plan_95["at100"] is False
    assert plan_95["currentHealthScore"] == 95
    assert plan_95["missingHealthScorePoints"] == 5
    assert plan_95["rawPenaltyTotal"] == 5
    assert sum(b["score_points_lost"] for b in plan_95["blockers"]) == 5
    assert plan_95["blockers"][0]["id"] == "missing_type"
    assert plan_95["blockers"][0]["sample_items"] == ["07_Knowledge/a.md", "07_Knowledge/b.md"]

    # Caso 2: saturacion en 0 (penalizacion bruta > 100)
    salud_0 = vault_audit.calcular_salud({
        "orphans": 20,          # -30
        "broken_links": 15,     # -20
        "missing_frontmatter": 10,  # -20
        "missing_cia": 10,      # -15
        "missing_tags": 10,     # -15
        "mermaid_errors": 10,   # -20
        "ap31": 20,             # -20
    })
    plan_0 = vault_audit._construir_to_reach_100(salud_0)
    assert plan_0["currentHealthScore"] == 0
    assert plan_0["rawPenaltyTotal"] == 140
    assert plan_0["pointsAboveZeroFloor"] == 40
    assert plan_0["blockersCount"] == 7
    assert "piso 0" in plan_0["summary"]


def test_vault_audit_real_siempre_expone_to_reach_100_y_cierra_huecos_en_next_actions(tmp_path):
    raiz = tmp_path / "vault-salud"
    for carpeta in ("00_System", "01_Projects/demo", "07_Knowledge", "99_Index"):
        (raiz / carpeta).mkdir(parents=True, exist_ok=True)
    # Nota sin type, status, cia, id, createdAt, updatedAt ni tags -> varias penalizaciones
    (raiz / "07_Knowledge" / "incompleta.md").write_text(
        "---\ntitle: Nota incompleta\n---\n# Nota incompleta\n\nContenido de prueba.\n",
        encoding="utf-8",
    )
    prev = vault_io.set_vault_root(raiz)
    try:
        res = vault_audit.vault_audit()
        assert res["ok"] is True
        plan = res["toReach100"]
        assert plan["at100"] is False
        assert plan["blockersCount"] >= 1
        assert sum(b["score_points_lost"] for b in plan["blockers"]) == plan["rawPenaltyTotal"]
        # Penalizaciones que antes eran invisibles en nextActions ahora aparecen con comando
        cats = {a.get("category") for a in res.get("nextActions", [])}
        assert "missing_type" in cats or "missing_status" in cats or "missing_cia" in cats
        for b in plan["blockers"]:
            assert b["remediation"]
            assert b["reason"]
    finally:
        vault_io.set_vault_root(prev)
