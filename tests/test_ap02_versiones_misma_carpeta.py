"""AP-02: la versión que el nombre declara, en la misma carpeta.

Desde v40.11 el catálogo declaraba AP-02 `cobertura_descubierta`: sus hermanas
AP-17 (similitud de título) y AP-18 (hash entre carpetas) se medían, y
`status-v1.md` junto a `status-v2.md` no lo veía nadie. El detector mide lo que
el nombre de fichero declara —el criterio por el que Obsidian resuelve el
enlace (AP-44)— y el catálogo pasa a `cobertura_parcial`, como AP-05: verde no
prueba que no haya versiones, prueba que ninguna lo dice en el nombre.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402
from vault_norms_catalog import NORM_CATALOG  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "04_Sessions", "07_Knowledge", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def _nota(root: Path, rel: str) -> Path:
    p = root / rel
    p.write_text(f"---\ntitle: {p.stem}\ntype: knowledge\n---\n\nCuerpo.\n", encoding="utf-8")
    return p


def test_ap02_ve_la_cadena_de_versiones_en_su_carpeta(tmp_path):
    root = _vault(tmp_path)
    notas = [
        _nota(root, "07_Knowledge/status.md"),
        _nota(root, "07_Knowledge/status-v2.md"),
        _nota(root, "07_Knowledge/status-final.md"),
        _nota(root, "07_Knowledge/status-v1-final.md"),
        _nota(root, "07_Knowledge/politica-de-backups.md"),
    ]
    [hallazgo] = va._detect_same_folder_versions(notas)
    assert hallazgo["folder"] == "07_Knowledge" and hallazgo["stem"] == "status"
    assert hallazgo["files"] == sorted(
        f"07_Knowledge/{n}" for n in
        ("status.md", "status-v2.md", "status-final.md", "status-v1-final.md"))


def test_ap02_no_confunde_carpetas_ni_sesiones_ni_nombres_sueltos(tmp_path):
    root = _vault(tmp_path)
    notas = [
        # Cada una en su carpeta: eso es AP-18 o AP-17, no AP-02.
        _nota(root, "01_Projects/status.md"),
        _nota(root, "07_Knowledge/status-v2.md"),
        # Sola con sufijo: no hay de qué ser versión.
        _nota(root, "07_Knowledge/api-v2.md"),
        # Sesiones: la fecha es el nombre y el sufijo nombra una release.
        _nota(root, "04_Sessions/2026-05-31.md"),
        _nota(root, "04_Sessions/2026-05-31-v095.md"),
        # Ninguna declara versión: dos notas distintas que comparten tronco no.
        _nota(root, "07_Knowledge/status-report.md"),
    ]
    assert va._detect_same_folder_versions(notas) == []


def test_ap02_llega_al_informe_del_audit(tmp_path):
    root = _vault(tmp_path)
    _nota(root, "07_Knowledge/status.md")
    _nota(root, "07_Knowledge/status-v2.md")
    informe = va.vault_audit()
    [hallazgo] = informe["issues"]["sameFolderVersions"]
    assert hallazgo["norm_code"] == "AP-02"
    assert "versiones AP-02" in informe["summary"]


def test_ap02_el_catalogo_dice_parcial_y_nombra_a_quien_la_mide():
    ap02 = next(n for n in NORM_CATALOG if n["code"] == "AP-02")
    assert ap02["tools_detecting"] == ["vault_audit"]
    assert not ap02.get("cobertura_descubierta")
    assert "status-actualizado" in ap02["cobertura_parcial"]
