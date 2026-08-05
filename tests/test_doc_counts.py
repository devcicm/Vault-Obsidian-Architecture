"""Contrato de vault_doc_counts — el guard anti-drift de cifras en documentación.

Estos tests protegen dos cosas distintas:

1. Que el guard *funcione* (detecta una cifra falsa, respeta el changelog,
   reescribe solo el número y no la frase).
2. Que la documentación del repo esté hoy alineada con el registro. Este
   segundo es el que falla cuando alguien escribe "34 grupos" a mano.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_doc_counts as vdc  # noqa: E402


# ─── El guard funciona ───────────────────────────────────────────────────────


def test_valores_vivos_se_derivan_del_registro():
    """Ninguna cifra del guard puede ser un literal congelado."""
    import vault_mcp_catalog
    import vault_registry
    from vault_norms import NORM_CATALOG

    assert vdc.count_tools_active() == len(vault_mcp_catalog.TOOLS_CATALOG)
    assert vdc.count_groups() == len(vault_mcp_catalog.GROUPS)
    assert vdc.count_norms() == len(NORM_CATALOG)
    assert vdc.count_sections() == len(vault_registry.standard_folders())


def test_cada_hecho_tiene_id_unico_valor_y_patrones():
    ids = [f["id"] for f in vdc.COUNTED_FACTS]
    assert len(ids) == len(set(ids)), f"ids duplicados: {ids}"
    for fact in vdc.COUNTED_FACTS:
        assert callable(fact["value"]), fact["id"]
        assert fact["patterns"], f"{fact['id']} sin patrones = hecho no vigilado"
        for pattern in fact["patterns"]:
            compiled = re.compile(pattern)
            assert compiled.groups >= 1, f"{pattern} no captura el número en group(1)"


def test_detecta_una_cifra_falsa(tmp_path, monkeypatch):
    doc = tmp_path / "FAKE.md"
    doc.write_text("El estándar tiene 999 tools activas hoy.\n", encoding="utf-8")
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    result = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert result["ok"] is False
    fallos = [m for m in result["mismatches"] if m["claimed"] == 999]
    assert fallos, result["mismatches"]
    assert fallos[0]["actual"] == vdc.count_tools_active()


def test_el_changelog_es_historia_y_no_se_vigila(tmp_path, monkeypatch):
    """Una cifra dentro del changelog es correcta para su versión."""
    doc = tmp_path / "FAKE.md"
    doc.write_text(
        "Hoy: 999 tools activas.\n\n## Changelog\n\n### v1 — 111 tools activas\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    result = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = {m["claimed"] for m in result["mismatches"]}
    assert 999 in reclamadas
    assert 111 not in reclamadas, "el guard entró en el changelog: eso es derogar historia"


def test_fix_reescribe_solo_el_numero(tmp_path, monkeypatch):
    doc = tmp_path / "FAKE.md"
    doc.write_text("Incluye 999 tools activas y nada más.\n", encoding="utf-8")
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    vdc.fix(docs=["FAKE.md"], include_slow=False)
    texto = doc.read_text(encoding="utf-8")
    assert texto == f"Incluye {vdc.count_tools_active()} tools activas y nada más.\n"


def test_fix_no_toca_el_changelog(tmp_path, monkeypatch):
    doc = tmp_path / "FAKE.md"
    original = "Hoy: 999 tools activas.\n\n## Changelog\n\n### v1 — 111 tools activas\n"
    doc.write_text(original, encoding="utf-8")
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    vdc.fix(docs=["FAKE.md"], include_slow=False)
    assert "111 tools activas" in doc.read_text(encoding="utf-8")


def test_un_registro_ilegible_no_tumba_el_guard(monkeypatch):
    """Un fallo al derivar una cifra se reporta, no revienta el proceso."""

    def _boom():
        raise RuntimeError("registro ilegible")

    fake = [{"id": "roto", "description": "x", "value": _boom, "patterns": [r"(\d+) x"]}]
    monkeypatch.setattr(vdc, "COUNTED_FACTS", fake)

    result = vdc.scan(docs=["README.md"], include_slow=False)
    assert result["ok"] is False
    assert result["errors"] and result["errors"][0]["fact"] == "roto"


# ─── La documentación del repo está alineada ─────────────────────────────────


def test_documentos_vigilados_existen():
    for rel in vdc.WATCHED_DOCS:
        assert (REPO_ROOT / rel).exists(), f"{rel} vigilado pero inexistente"


def test_ninguna_cifra_del_repo_miente():
    """El test de mayor palanca: falla en cuanto un doc envejece.

    Se omite el conteo de tests (`slow`) porque exigiría lanzar pytest desde
    dentro de pytest. Lo cubre el paso de CI, que corre sin `--no-slow`.
    """
    result = vdc.scan(include_slow=False)
    assert result["ok"], "\n".join(
        f"{m['file']}:{m['line']} [{m['fact']}] dice {m['claimed']}, real {m['actual']}"
        for m in result["mismatches"]
    ) or str(result["errors"])


def test_la_tool_esta_en_el_catalogo_canonico():
    import vault_mcp_catalog

    assert "vault_doc_counts" in vault_mcp_catalog.TOOLS_CATALOG
    agrupadas = {t for tools in vault_mcp_catalog.GROUPS.values() for t in tools}
    assert "vault_doc_counts" in agrupadas
    assert vault_mcp_catalog.TOOLS_CATALOG["vault_doc_counts"]["group"] == "Normas"
