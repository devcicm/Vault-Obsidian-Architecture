"""Los backlinks del audit se resuelven como los resuelve Obsidian (AP-44).

`_build_indexes` ya leía `aliases:` y la ruta con carpeta para decidir si un
enlace está **roto**, pero el índice de backlinks emparejaba solo por nombre de
fichero normalizado. El mismo enlace salía a la vez «no roto» y «sin destino»:
`[[Nombre Legible]]`, `[[05_Patterns/destino]]` o `[[destino#sección]]` dejaban
a la nota enlazada como huérfana, y a la que enlaza sin wikilink saliente.
Medido el 2026-10-09 al preparar el núcleo del vault por fan-in (deuda #11),
que se apoya en este mismo índice.

El criterio es el del dueño canónico —`vault_lib.resolver_wikilink`—, **sumado**
al emparejamiento que ya había: el arreglo solo puede quitar huérfanas falsas,
nunca estrenar una.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402

FM = "---\nstatus: draft\ntype: reference\ntags: [x]\n---\n\n"
DESTINO = (
    "---\nstatus: draft\ntype: reference\ntags: [x]\n"
    "aliases: [Nombre Legible]\n---\n\n# Destino\n\ntexto\n"
)


def _vault(tmp_path: Path, enlace: str) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "05_Patterns", "06_Decisions", "99_Index"):
        (root / sec).mkdir(parents=True)
    (root / "05_Patterns" / "destino.md").write_text(DESTINO, encoding="utf-8")
    (root / "06_Decisions" / "origen.md").write_text(
        FM + f"# Origen\n\nver {enlace}\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


@pytest.mark.parametrize("enlace", [
    "[[Nombre Legible]]",
    "[[05_Patterns/destino]]",
    "[[destino#Destino]]",
    "[[../05_Patterns/destino]]",
    "[[destino]]",
    "[[Destino]]",
])
def test_la_nota_enlazada_no_es_huerfana(tmp_path, enlace):
    _vault(tmp_path, enlace)
    r = va.vault_audit()
    huerfanas = {o["path"] for o in r["issues"]["orphans"]}
    assert "05_Patterns/destino.md" not in huerfanas


def test_el_backlink_lleva_al_origen(tmp_path):
    _vault(tmp_path, "[[Nombre Legible|otro texto]]")
    notas = sorted((tmp_path / "v").rglob("*.md"))
    backlinks, _ = va._build_indexes(notas)
    assert backlinks["destino"] == {"origen"}


def test_limite_declarado_los_homonimos_comparten_entrantes(tmp_path):
    """Deuda `backlinks_del_audit_indexados_por_nombre`: la clave es el nombre.

    Cuando el índice pase a ruta, este test falla y la deuda se salda.
    """
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "05_Patterns/code", "11_Code/ans"):
        (root / sec).mkdir(parents=True)
    (root / "05_Patterns/code/homonima.md").write_text(FM + "# A\n", encoding="utf-8")
    (root / "11_Code/ans/homonima.md").write_text(FM + "# B\n", encoding="utf-8")
    (root / "05_Patterns/origen.md").write_text(FM + "# O\n\n[[code/homonima]]\n",
                                                encoding="utf-8")
    vault_io.set_vault_root(root)
    r = va.vault_audit()
    huerfanas = {o["path"] for o in r["issues"]["orphans"]}
    assert "11_Code/ans/homonima.md" not in huerfanas


def test_un_enlace_roto_sigue_sin_backlink(tmp_path):
    _vault(tmp_path, "[[no-existe]]")
    notas = sorted((tmp_path / "v").rglob("*.md"))
    backlinks, _ = va._build_indexes(notas)
    assert not backlinks.get("destino")
