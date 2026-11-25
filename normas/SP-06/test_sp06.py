"""Tests de paquete de norma SP-06 (Madurez progresiva XP / Augmented Coding)."""

from pathlib import Path

import vault_norms_catalog
from vault.kernel.normativa.xp import validar_politica_xp


def test_sp06_politica_xp_y_compuerta_tdd():
    norma = vault_norms_catalog.norma_por_codigo("SP-06")
    assert norma is not None
    assert norma["enforcement"] == "guard"
    assert "vault_requirement_save" in norma["tools_enforcing"]
    assert "vault_code_review" in norma["tools_enforcing"]
    assert validar_politica_xp({}) is None
    assert validar_politica_xp({"xp_level": 2}) is None
    assert validar_politica_xp({"xp_level": 5}) is not None
    assert validar_politica_xp({"xp_level": 4}) is not None
    assert validar_politica_xp({
        "xp_level": 4,
        "xp_prerequisites": {"tdd_pass": True, "human_pair_review": True},
    }) is None
    assert (Path(__file__).parent / "porque.md").is_file()
