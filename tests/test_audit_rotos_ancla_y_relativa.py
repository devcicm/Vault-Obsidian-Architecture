"""Un enlace con `#ancla` o con ruta relativa no está roto si Obsidian lo abre.

`_detect_broken_links` normalizaba el enlace entero, ancla incluida, y solo
casaba rutas escritas desde la raíz. `[[nota#Sección]]` y
`[[../carpeta/nota]]` salían rotos aunque Obsidian los abre (AP-44). El
criterio que faltaba ya tenía dueño: `vault_lib.resolver_wikilink` (AP-57),
que quita el ancla y resuelve la ruta relativa contra la carpeta de la nota.
Se **suma** a lo que ya resolvía, así que el arreglo solo quita rotos falsos.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402

FM = "---\nstatus: draft\ntype: reference\ntags: [x]\n---\n\n"


def _vault(tmp_path: Path, enlace: str) -> None:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "05_Patterns", "06_Decisions"):
        (root / sec).mkdir(parents=True)
    (root / "05_Patterns" / "destino.md").write_text(FM + "# Destino\n\n## Sección\n",
                                                     encoding="utf-8")
    (root / "06_Decisions" / "origen.md").write_text(FM + f"# Origen\n\nver {enlace}\n",
                                                     encoding="utf-8")
    vault_io.set_vault_root(root)


@pytest.mark.parametrize("enlace", [
    "[[destino#Sección]]",
    "[[destino#^bloque]]",
    "[[05_Patterns/destino#Sección]]",
    "[[../05_Patterns/destino]]",
    "[[./../05_Patterns/destino|texto]]",
])
def test_el_enlace_que_obsidian_abre_no_esta_roto(tmp_path, enlace):
    _vault(tmp_path, enlace)
    assert va.vault_audit()["issues"]["brokenLinks"] == []


def test_la_ruta_parcial_casa_como_sufijo(tmp_path):
    """`[[ans/README]]` desde un índice: Obsidian casa el sufijo de la ruta.

    Fue la mayor parte de lo medido (regla 7, 2026-10-09): /vcloud 20 → 6, que
    son exactamente los seis que da `vault_foreign_check`, el control; /ans
    151 → 74.
    """
    import vault_io

    root = tmp_path / "v"
    (root / "01_Projects" / "ans").mkdir(parents=True)
    (root / "00_System").mkdir()
    (root / "01_Projects" / "ans" / "README.md").write_text(FM + "# R\n", encoding="utf-8")
    (root / "01_Projects" / "nota.md").write_text(
        FM + "# N\n\n[[ans/README]] y [[otro/README]]\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    rotos = va.vault_audit()["issues"]["brokenLinks"]
    assert [e["link"] for e in rotos] == ["otro/README"]


@pytest.mark.parametrize("enlace", [
    "[[no-existe#Sección]]",
    "[[../06_Decisions/destino]]",
    "[[otra-carpeta/destino]]",
])
def test_el_enlace_que_obsidian_no_abre_sigue_roto(tmp_path, enlace):
    _vault(tmp_path, enlace)
    rotos = va.vault_audit()["issues"]["brokenLinks"]
    assert [e["from"] for e in rotos] == ["06_Decisions/origen.md"]
