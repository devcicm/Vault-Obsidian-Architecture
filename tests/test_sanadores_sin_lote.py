"""Sanadores que todavía escriben nota a nota, fuera de `escrituras_en_lote`.

AP-47: `vault_io.escrituras_en_lote()` hace que la sección, la búsqueda y el
grafo se regeneren una vez por lote y no una vez por nota. Lo abren
`vault_frontmatter_completar` y la ruta clasificada de `vault_graph_fix`
(`apply_classified_fixes`); el resto de `vault_norms_catalog.SANADORES` y la otra
ruta de `vault_graph_fix` (`apply_fix`) no. Está declarado como deuda
(`sanadores_sin_lote`), y este test fija el límite medido: falla en cuanto un
sanador abre el lote —la deuda encoge y hay que anotarlo— y en cuanto aparece un
sanador nuevo sin él, que es deuda nueva.
"""

import importlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_blueprint as bp  # noqa: E402
from vault_norms_catalog import SANADORES  # noqa: E402

#: El límite medido el 2026-10-14 sobre 35f5bad; encoge con cada sanador que
#: entra (2026-10-16: `vault_fix_brackets`).
SIN_LOTE = {
    "vault_frontmatter_heal",
    "vault_supersede",
    "vault_project",
    "vault_norms_engine",
}


def _abre_el_lote(tool: str) -> bool:
    modulo = importlib.import_module(tool)
    return "escrituras_en_lote" in Path(modulo.__file__).read_text(encoding="utf-8")


def test_la_deuda_de_sanadores_sin_lote_esta_declarada():
    d = next((d for d in bp.DEUDA_DECLARADA if d["id"] == "sanadores_sin_lote"), None)
    assert d is not None
    assert d["estado"] == "pendiente" or d.get("sostenida_por")


def test_limite_declarado_sanadores_sin_lote():
    medidos = {t for t in SANADORES if not _abre_el_lote(t)}
    assert medidos == SIN_LOTE, (
        f"sin lote ahora: {sorted(medidos)}; declarados: {sorted(SIN_LOTE)}. "
        "Si encogió, actualiza la deuda `sanadores_sin_lote`; si creció, el "
        "sanador nuevo tiene que abrir `vault_io.escrituras_en_lote()` (AP-47)."
    )


def test_limite_declarado_apply_fix_sin_lote():
    from vault.grafo import graph_fix

    assert "escrituras_en_lote" in inspect.getsource(graph_fix.apply_classified_fixes)
    assert "escrituras_en_lote" not in inspect.getsource(graph_fix.apply_fix)


# --- Cada sanador que entra en el lote --------------------------------------
# El rojo de cada uno: dos notas de la misma sección escritas por el sanador
# regeneraban la sección dos veces. El árbol con lote y sin él se comparó
# sobre copias de /ans y /vcloud antes de cada commit.

def _secciones_regeneradas(monkeypatch):
    import vault_section_index as vsi

    secciones = []
    original = vsi.vault_section_index

    def contado(folder, *a, **kw):
        secciones.append(folder)
        return original(folder, *a, **kw)

    monkeypatch.setattr(vsi, "vault_section_index", contado)
    return secciones


def _vault_con(tmp_path, monkeypatch, notas):
    import vault_io

    (tmp_path / "00_System").mkdir()
    for rel, texto in notas.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(texto, encoding="utf-8")
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    original = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    return original


def test_ap47_fix_brackets_escribe_en_lote(tmp_path, monkeypatch):
    import vault_fix_brackets
    import vault_io

    rota = "---\ntitle: {0}\n---\nver [[]] aquí\n"
    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/a.md": rota.format("a"), "07_Knowledge/b.md": rota.format("b")})
    try:
        secciones = _secciones_regeneradas(monkeypatch)
        r = vault_fix_brackets.vault_fix_brackets(apply=True)
    finally:
        vault_io.set_vault_root(original)
    assert sorted(r["files_modified"]) == ["07_Knowledge/a.md", "07_Knowledge/b.md"], r
    assert secciones == ["07_Knowledge"], secciones
