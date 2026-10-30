"""A-13 — límite declarado: el servidor MCP no distingue perfiles por token.

`vault-mcp-server.mjs` acepta un único Bearer (`resolverTokenHttp`): quien lo
tiene llama a toda tool, incluidas `vault_delete` y `vault_standard_upgrade`.
Este test fija el hueco y falla el día que exista una tabla de perfiles por
token o por tool: entonces la deuda `mcp_sin_perfiles_por_token` pasa a `saldada`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUENTE = (ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(encoding="utf-8")


def test_limite_declarado_mcp_sin_perfiles_por_token():
    assert "function resolverTokenHttp()" in FUENTE
    assert "VAULT_MCP_TOKENS" not in FUENTE
    for marca in ("PERFILES_TOKEN", "perfilDeToken", "permisosPorToken"):
        assert marca not in FUENTE, f"hay perfiles por token ({marca}): salda la deuda"
