"""AP-17 sanado: un par con `superseded_by:` hacia la otra nota ya no es deuda.

Medido el 2026-10-07 en una copia de /ans: siete gemelas migradas a
`10_Migrated/` con el mismo `title:` que su original. El procedimiento de
sanación pide anotar `superseded_by:` en la sustituida, y `context_pack` ya la
baja (da34926); pero `vault_audit` seguía penalizando el par como si nadie
hubiera decidido cuál manda. La anotación es esa decisión, y el detector la
tiene que leer con el criterio del consumidor (AP-44): el enlace se resuelve
por nombre de fichero y `aliases:`, nunca por `title:`.
"""

import pytest

import vault_audit
import vault_io


def _nota(vault, rel, fm):
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm}\n---\n\n# Guía MCP\n\nCuerpo.\n", encoding="utf-8")
    return p


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "00_System").mkdir(parents=True)
    vault_io.set_vault_root(v)
    return v


def _pares(vault, notas):
    resueltos = []
    pares = vault_audit._detect_canonical_shadow(notas, resueltos=resueltos)
    return pares, resueltos


def test_ap17_un_par_anotado_sale_de_la_deuda_y_se_publica_resuelto(vault):
    canonica = _nota(vault, "07_Knowledge/mcp-agent-guide.md", "title: Mcp Agent Guide")
    gemela = _nota(vault, "10_Migrated/MCP_AGENT_GUIDE.md",
                   'title: Mcp Agent Guide\nsuperseded_by: "[[mcp-agent-guide]]"')
    pares, resueltos = _pares(vault, [canonica, gemela])
    assert pares == []
    assert resueltos == [{"sustituidas": ["10_Migrated/MCP_AGENT_GUIDE.md"],
                          "canonica": "07_Knowledge/mcp-agent-guide.md",
                          "similarity": 1.0}]


def test_ap17_superseded_by_resuelve_por_alias_y_no_por_titulo(vault):
    canonica = _nota(vault, "07_Knowledge/guia.md",
                     "title: Mcp Agent Guide\naliases: [Guia MCP]")
    gemela = _nota(vault, "10_Migrated/MCP_AGENT_GUIDE.md",
                   'title: Mcp Agent Guide\nsuperseded_by: "[[Guia MCP]]"')
    assert _pares(vault, [canonica, gemela])[0] == []

    por_titulo = _nota(vault, "10_Migrated/otra.md",
                       'title: Mcp Agent Guide\nsuperseded_by: "[[Mcp Agent Guide]]"')
    pares, _ = _pares(vault, [canonica, por_titulo])
    assert len(pares) == 1, "un title: no resuelve un wikilink en Obsidian"


@pytest.mark.parametrize("valor", [
    '""',                         # vacío
    '"[[no-existe]]"',            # roto
    '"[[politica-de-backups]]"',  # apunta a una tercera, no a la del par
])
def test_ap17_una_anotacion_que_no_lleva_a_la_otra_no_resuelve(vault, valor):
    canonica = _nota(vault, "07_Knowledge/mcp-agent-guide.md", "title: Mcp Agent Guide")
    _nota(vault, "07_Knowledge/politica-de-backups.md", "title: Politica de backups")
    gemela = _nota(vault, "10_Migrated/MCP_AGENT_GUIDE.md",
                   f"title: Mcp Agent Guide\nsuperseded_by: {valor}")
    pares, resueltos = _pares(vault, [canonica, gemela])
    assert len(pares) == 1 and resueltos == []


def test_ap17_un_enlace_ambiguo_no_resuelve(vault):
    """Dos notas responden a `[[guia]]`: elegir una sería inventar la identidad."""
    a = _nota(vault, "07_Knowledge/guia.md", "title: Mcp Agent Guide")
    _nota(vault, "05_Patterns/guia.md", "title: Otra cosa")
    gemela = _nota(vault, "10_Migrated/MCP_AGENT_GUIDE.md",
                   'title: Mcp Agent Guide\nsuperseded_by: "[[guia]]"')
    assert len(_pares(vault, [a, gemela])[0]) == 1


def test_ap17_dos_gemelas_sustituidas_por_la_misma_canonica_no_compiten(vault):
    """Medido en la copia de /ans: dos copias migradas de la misma guía, las
    dos anotadas hacia la canónica, seguían emparejadas entre sí."""
    canonica = _nota(vault, "07_Knowledge/mcp-agent-guide.md", "title: Mcp Agent Guide")
    a = _nota(vault, "10_Migrated/direct/MCP_AGENT_GUIDE.md",
              'title: Mcp Agent Guide\nsuperseded_by: "[[mcp-agent-guide]]"')
    b = _nota(vault, "10_Migrated/excluded/MCP_AGENT_GUIDE.md",
              'title: Mcp Agent Guide\nsuperseded_by: "[[mcp-agent-guide]]"')
    pares, resueltos = _pares(vault, [canonica, a, b])
    assert pares == []
    assert len(resueltos) == 3
