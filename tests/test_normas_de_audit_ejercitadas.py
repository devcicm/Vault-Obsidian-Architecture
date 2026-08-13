"""AP-03, AP-17 y AP-30: cubiertas por mención, no por prueba (v40.16).

La capa 4 del plano daba una norma por cubierta si **algún** fichero de
`tests/` contenía su código en cualquier sitio — un docstring que la citaba de
pasada bastaba. Estas tres lo estaban así: `vault_audit` las penaliza en
`PENALIZACIONES`, ningún test tocaba su detector, y como la baseline de la capa
4 solo encoge, la certificación falsa era irreversible.

Aquí se ejercita el detector de cada una contra un vault mínimo. No es lo mismo
que probar el enforcement completo, pero distingue lo que la mención no
distinguía: que el detector existe, corre y ve el caso que la norma describe.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def _nota(root: Path, rel: str, fm: str, cuerpo: str = "Cuerpo de la nota.\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm}\n---\n\n{cuerpo}", encoding="utf-8")
    return p


def test_ap03_ve_la_seccion_cuyo_indice_es_un_stub(tmp_path):
    """AP-03: una carpeta con `index.md` y ninguna nota real."""
    root = _vault(tmp_path)
    (root / "07_Knowledge").mkdir()
    (root / "07_Knowledge" / "index.md").write_text("# vacia\n", encoding="utf-8")
    _nota(root, "01_Projects/algo.md", "title: Algo\ntype: project")

    vacias = {e["folder"] for e in va._detect_empty_indexes()}
    assert "07_Knowledge" in vacias, "AP-03 no ve la seccion sin notas"
    assert "01_Projects" not in vacias, "AP-03 marca una seccion que si tiene notas"


def test_ap17_ve_el_par_canonico_y_su_sombra(tmp_path):
    """AP-17: dos notas cuyo titulo se parece por encima del umbral."""
    root = _vault(tmp_path)
    a = _nota(root, "01_Projects/servicio-de-facturacion.md",
              "title: Servicio de facturacion\ntype: project")
    b = _nota(root, "07_Knowledge/servicio-de-facturacion-v2.md",
              "title: Servicio de facturacion v2\ntype: knowledge")
    solo = _nota(root, "07_Knowledge/politica-de-backups.md",
                 "title: Politica de backups\ntype: knowledge")

    pares = va._detect_canonical_shadow([a, b, solo])
    involucradas = {n for par in pares for k, n in par.items() if k.startswith("note")}
    assert pares, "AP-17 no ve el par canonico/sombra"
    assert not any("politica-de-backups" in str(n) for n in involucradas), (
        "AP-17 empareja una nota que no se parece a ninguna"
    )


def test_ap30_ve_la_nota_sin_clasificacion_cia(tmp_path):
    """AP-30: nota de contenido sin la triada de confidencialidad."""
    root = _vault(tmp_path)
    sin = _nota(root, "01_Projects/sin-cia.md",
                "title: Sin CIA\ntype: project\nstatus: active\ntags: [x]")
    con = _nota(
        root, "01_Projects/con-cia.md",
        "title: Con CIA\ntype: project\nstatus: active\ntags: [x]\n"
        "cia_integrity: high\ncia_availability: normal\ncia_sensitivity: internal",
    )

    faltan = va._detect_missing_metadata([sin, con])["missing_cia"]
    rutas = {e.get("note") or e.get("path") for e in faltan}
    assert any("sin-cia" in str(r) for r in rutas), "AP-30 no ve la nota sin CIA"
    assert not any("con-cia" in str(r) for r in rutas), (
        "AP-30 marca una nota que si declara la triada"
    )
