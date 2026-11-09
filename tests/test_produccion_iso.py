"""Promesas de producto que vienen de normas ISO: SBOM (5962/5230) y política
de vulnerabilidades (29147).

SECURITY.md describe una superficie, y una descripción de seguridad que el
código ya no cumple es peor que ninguna: quien la lee baja la guardia. Por eso
cada afirmación de «Superficie expuesta» se contrasta aquí con el código que la
hace verdad.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

import vault_produccion  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def _fila(id_):
    (f,) = [f for f in vault_produccion.medir()["filas"] if f["id"] == id_]
    return f


def test_las_dos_promesas_estan_cubiertas_y_ejercidas():
    for id_ in ("sbom_y_licencias", "politica_de_vulnerabilidades"):
        f = _fila(id_)
        assert f["estado"] == "cubierta" and f["ejercida"], f
        assert f["hueco_conocido"], id_


def test_sin_security_md_la_promesa_queda_sin_ejecutor(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_produccion, "RAIZ", tmp_path)
    assert vault_produccion._politica_de_vulnerabilidades() is False
    (tmp_path / "SECURITY.md").write_text("# Seguridad\n\nescribid un issue\n", encoding="utf-8")
    assert vault_produccion._politica_de_vulnerabilidades() is False
    assert vault_produccion._sbom_en_la_ci() is False


def test_security_md_no_afirma_lo_que_el_codigo_no_hace():
    texto = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    servidor = (ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(encoding="utf-8")
    ingest = gi.codigo_de(SCRIPTS / "vault_ingest.py").read_text(encoding="utf-8")
    tokens = gi.codigo_de(SCRIPTS / "vault_token_service.py").read_text(encoding="utf-8")
    errores = (ROOT / "vault" / "kernel" / "errores.py").read_text(encoding="utf-8")
    afirmaciones = {
        # El bind configurable (integrado del arbol del MiniServer) mantiene
        # 127.0.0.1 como DEFAULT y rechaza comodines al arrancar.
        "127.0.0.1": 'let SSE_HOST = "127.0.0.1"' in servidor
        and 'not allowed' in servidor,
        "VAULT_MCP_TOKEN": "process.env.VAULT_MCP_TOKEN" in servidor,
        "VAULT_MCP_TOKENS": "process.env.VAULT_MCP_TOKENS" in servidor
        and "permitidaPorToken(tool, session)" in servidor,
        "tiempo constante": "timingSafeEqual(" in servidor,
        "cabecera `Origin`": "rechazar(403" in servidor,
        "--allow-network": "NETWORK_DISABLED" in ingest,
        "VAULT_TOKEN_SERVICE_TOKEN": 'ENV_TOKEN = "VAULT_TOKEN_SERVICE_TOKEN"' in tokens
        and "hmac.compare_digest(" in tokens and 'DEFAULT_HOST = "127.0.0.1"' in tokens,
        "VAULT_DEBUG=1": "incluir_traceback: bool = False" in errores,
    }
    for frase, cierto in afirmaciones.items():
        assert frase in texto, frase
        assert cierto, f"SECURITY.md afirma «{frase}» y el código ya no lo hace"


def test_el_readme_manda_a_security_md():
    assert "[SECURITY.md](SECURITY.md)" in (ROOT / "README.md").read_text(encoding="utf-8")
