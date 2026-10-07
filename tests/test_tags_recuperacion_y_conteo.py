"""`vault_tags` sin registro y el recuento de notas etiquetadas.

Medido el 2026-10-07 sobre copias de /ans y /vcloud (regla 7):

- Sin `00_System/tag-registry.json`, `--audit` y `--suggest` devolvían
  `INDEX_NOT_FOUND` con la recuperación genérica del catálogo,
  `vault_reindex --graph`, que no crea ese registro: quien seguía `run_tool`
  al pie de la letra volvía al mismo error. Lo crea `vault_tags` sin
  argumentos (`vault_tags_rebuild`).
- `total_tagged_notes` sumaba las notas de cada tag: una nota con tres tags
  contaba tres veces (1684 «notas etiquetadas» en un vault de 467). El índice
  humano ya lo llamaba «referencias»; el campo prometía notas.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_tags as vt  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "07_Knowledge").mkdir()
    (root / "07_Knowledge" / "a.md").write_text(
        "---\ntitle: A\ntype: concept\ntags: [api, demo]\n---\n# A\n", encoding="utf-8")
    (root / "07_Knowledge" / "b.md").write_text(
        "---\ntitle: B\ntype: concept\ntags: [api]\n---\n# B\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def test_sin_registro_el_audit_receta_al_productor_del_registro(tmp_path):
    _vault(tmp_path)
    env = vt.vault_tags_audit()
    assert env["error_code"] == "INDEX_NOT_FOUND"
    assert env["recovery"]["tool"] == "vault_tags"
    assert env["recovery"]["args"] == []


def test_sin_registro_suggest_receta_al_productor_del_registro(tmp_path):
    root = _vault(tmp_path)
    env = vt.vault_tags_suggest(str(root / "07_Knowledge" / "a.md"))
    assert env["error_code"] == "INDEX_NOT_FOUND"
    assert env["recovery"]["tool"] == "vault_tags"


def test_seguir_la_recuperacion_crea_el_registro(tmp_path):
    root = _vault(tmp_path)
    vt.vault_tags_rebuild()
    assert (root / "00_System" / "tag-registry.json").exists()
    assert vt.vault_tags_audit()["ok"] is True


def test_total_tagged_notes_cuenta_notas_distintas(tmp_path):
    """a lleva [api, demo] y b [api]: dos notas etiquetadas, tres usos."""
    _vault(tmp_path)
    env = vt.vault_tags_rebuild()
    assert env["total_tagged_notes"] == 2
    assert env["total_tag_uses"] == 3
    import json
    reg = json.loads((tmp_path / "v" / "00_System" / "tag-registry.json").read_text(encoding="utf-8"))
    assert reg["total_tagged_notes"] == 2
    assert reg["total_tag_uses"] == 3
    assert vt.vault_tags_audit()["total_tagged_notes"] == 2
