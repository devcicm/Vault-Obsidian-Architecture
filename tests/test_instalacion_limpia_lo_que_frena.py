"""La guía de instalación limpia avisa de lo que frena a quien la sigue a ciegas.

R7 (2026-10-15): instalación ciega con wheel limpia en un venv nuevo, siguiendo
solo `docs/INSTALACION-LIMPIA.md`. Todo funcionó salvo dos cosas que la guía
no decía: la primera escritura sale con `missing_agent` porque nadie le contó
al consumidor que exporte `VAULT_AGENT` (AP-16), y el servidor MCP arranca
avisando de tools «retiradas» —las de gobernanza del estándar, que la wheel de
producto deja fuera a propósito— sin que nada le diga que es lo esperado.
"""

from pathlib import Path

GUIA = Path(__file__).resolve().parent.parent / "docs" / "INSTALACION-LIMPIA.md"


def test_la_guia_pide_vault_agent_antes_de_escribir():
    texto = GUIA.read_text(encoding="utf-8")
    assert "VAULT_AGENT" in texto and "missing_agent" in texto


def test_la_guia_explica_el_aviso_de_tools_retiradas():
    texto = GUIA.read_text(encoding="utf-8")
    assert "retiradas" in texto
    assert "gobernanza" in texto
