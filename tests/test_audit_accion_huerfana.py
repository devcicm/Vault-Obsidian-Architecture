"""La acción sugerida para una huérfana no promete lo que el audit no hace.

Hasta v41.0 la acción de `vault_audit` para cada huérfana:

- citaba `"norm": "AP-13"`, que es «timestamps inválidos o incompletos en
  frontmatter». `PENALIZACIONES` declara las huérfanas como métrica **sin
  norma** (`"norma": None`) y explica por qué. Dos respuestas distintas a la
  misma pregunta en el mismo audit (AP-57);
- mandaba «marcar la nota como reference (no necesita backlinks)».
  `_detect_orphans` no mira `type`: una nota `type: reference` sin entrantes
  sigue saliendo huérfana. El agente que seguía la receta no cambiaba nada
  (AP-44: el consejo se mide con el criterio del detector, no con el propio).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402
from vault_audit_catalog import PENALIZACIONES  # noqa: E402


def _acciones_huerfanas(tmp_path: Path):
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    (root / "07_Knowledge" / "sola.md").write_text(
        "---\ntitle: sola\ntype: reference\nstatus: draft\ntags: [x]\n---\n\n# sola\n",
        encoding="utf-8",
    )
    vault_io.set_vault_root(root)
    informe = va.vault_audit()
    huerfanas = {o["path"] for o in informe["issues"]["orphans"]}
    acciones = [a for a in informe.get("nextActions", []) if a.get("category") == "orphan"]
    return huerfanas, acciones


def test_la_norma_citada_es_la_que_declara_penalizaciones(tmp_path):
    _huerfanas, acciones = _acciones_huerfanas(tmp_path)
    assert acciones, "el audit no sugirió nada para la huérfana"
    declarada = next(p["norma"] for p in PENALIZACIONES if p["id"] == "orphans")
    assert {a["norm"] for a in acciones} == {declarada}


def test_no_promete_que_type_reference_la_exima(tmp_path):
    huerfanas, acciones = _acciones_huerfanas(tmp_path)
    # El hecho: `type: reference` no saca a la nota de las huérfanas...
    assert "07_Knowledge/sola.md" in huerfanas
    # ...así que la receta no puede ofrecerlo como salida.
    for a in acciones:
        assert "reference" not in a["command"], a["command"]
