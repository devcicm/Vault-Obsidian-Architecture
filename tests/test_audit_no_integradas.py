"""Una nota enlazada solo desde un índice no está integrada en el vault.

Medido el 2026-10-07 en un vault ajeno (solo lectura): 356 de 510 notas de
contenido tenían como único enlace entrante el de un `index.md` de sección y
351 no enlazaban a ninguna otra nota. Para `_detect_orphans` ninguna es
huérfana —el índice les da un backlink— y el audit las daba por conectadas.
Están listadas, no integradas: nadie las cita y ellas no citan a nadie.

La medida es **recomendada**: se publica en `issues.notIntegrated` y en
`stats`, pero no entra en `PENALIZACIONES` ni mueve `healthScore`. Penalizarla
cambiaría la cifra que los consumidores ya leen por un criterio que todavía no
tiene norma, y `test_salud_por_familias` vigila justo ese cálculo.

Disjunta con las huérfanas: una nota sin ningún entrante es huérfana y no se
cuenta dos veces.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "05_Patterns"):
        (root / sec).mkdir(parents=True)
    return root


def _nota(root: Path, rel: str, cuerpo: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nstatus: draft\ntype: reference\ntags: [x]\n---\n\n# n\n\n" + cuerpo,
        encoding="utf-8",
    )


def _no_integradas(root: Path):
    import vault_io

    vault_io.set_vault_root(root)
    notas = va._get_active_notes(None, include_structural=True)
    backlinks, _ = va._build_indexes(notas)
    contenido = va._get_active_notes(None, include_structural=False)
    return {
        o["path"].replace("\\", "/")
        for o in va._detect_no_integradas(contenido, backlinks, notas)
    }


def test_la_nota_enlazada_solo_desde_el_indice_no_esta_integrada(tmp_path):
    root = _vault(tmp_path)
    _nota(root, "05_Patterns/index.md", "- [[listada]]\n")
    _nota(root, "05_Patterns/listada.md")

    assert "05_Patterns/listada.md" in _no_integradas(root)


def test_un_enlace_desde_otra_nota_la_integra(tmp_path):
    root = _vault(tmp_path)
    _nota(root, "05_Patterns/index.md", "- [[citada]]\n")
    _nota(root, "05_Patterns/citada.md")
    _nota(root, "01_Projects/proyecto.md", "Usa [[citada]].\n")

    assert "05_Patterns/citada.md" not in _no_integradas(root)


def test_un_enlace_saliente_la_integra(tmp_path):
    root = _vault(tmp_path)
    _nota(root, "05_Patterns/index.md", "- [[cita-a-otra]]\n")
    _nota(root, "05_Patterns/cita-a-otra.md", "Ver [[proyecto]].\n")
    _nota(root, "01_Projects/proyecto.md")

    assert "05_Patterns/cita-a-otra.md" not in _no_integradas(root)


def test_la_huerfana_no_se_cuenta_dos_veces(tmp_path):
    root = _vault(tmp_path)
    _nota(root, "05_Patterns/sola.md")

    assert "05_Patterns/sola.md" not in _no_integradas(root)


def test_las_exclusiones_son_las_de_las_huerfanas(tmp_path):
    """Sistema y sesiones no necesitan enlaces; ya lo decide `_detect_orphans`."""
    root = _vault(tmp_path)
    _nota(root, "04_Sessions/index.md", "- [[2026-10-07]]\n")
    _nota(root, "04_Sessions/2026-10-07.md")

    assert "04_Sessions/2026-10-07.md" not in _no_integradas(root)


def test_no_mueve_el_health_score():
    """Recomendada: no tiene fila en `PENALIZACIONES`."""
    from vault_audit_catalog import PENALIZACIONES

    ids = {p["id"] for p in PENALIZACIONES}
    assert not ids & {"not_integrated", "notIntegrated", "no_integradas"}
