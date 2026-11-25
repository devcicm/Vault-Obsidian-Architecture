"""Tests de paquete de norma SP-05 (Fábrica de Conocimiento)."""

from pathlib import Path

import vault_mcp_catalog
import vault_norms_catalog


def test_sp05_circuito_cerrado_ejecutor_curador():
    norma = vault_norms_catalog.norma_por_codigo("SP-05")
    assert norma is not None
    assert norma["enforcement"] == "guard"
    assert "ejecutor" in vault_mcp_catalog.PERFILES_DE_TOKEN
    assert vault_mcp_catalog.perfil_minimo(vault_mcp_catalog.TOOLS_CATALOG["vault_ronda"]) == "ejecutor"
    assert vault_mcp_catalog.perfil_minimo(vault_mcp_catalog.TOOLS_CATALOG["vault_propagate"]) == "operador"
    assert vault_mcp_catalog.perfil_minimo(vault_mcp_catalog.TOOLS_CATALOG["vault_write"]) == "operador"
    assert (Path(__file__).parent / "porque.md").is_file()
