"""Un frontmatter que no se puede leer no sale igual que uno que no existe.

Medido el 2026-10-05 con la wheel 40.35 contra un vault real: un ADR con dos
puntos sin escapar en el `title` hacía fallar el YAML, y `vault_read` devolvía
`ok: true` con `meta: {}` — lo mismo que una nota sin frontmatter. El agente
que leía la nota no tenía forma de saber que sus metadatos estaban ahí y rotos
(AP-51: un vacío indistinguible de un resultado legítimo).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _leer(tmp_path, texto):
    import vault_io
    import vault_read

    (tmp_path / "00_System").mkdir(exist_ok=True)
    (tmp_path / "nota.md").write_text(texto, encoding="utf-8")
    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    try:
        return vault_read.vault_read("nota.md")
    finally:
        vault_io.set_vault_root(anterior)


def test_ap51_frontmatter_roto_se_declara(tmp_path):
    r = _leer(tmp_path, "---\nid: adr\ntitle: ADR-004 — Algoritmo: eliminar\n---\n\ncuerpo\n")
    assert r["ok"] is True and r["meta"] == {}
    assert r.get("frontmatter_error"), r


def test_ap51_sin_frontmatter_no_es_un_error(tmp_path):
    r = _leer(tmp_path, "# Nota\n\ncuerpo\n")
    assert r["ok"] is True and r["meta"] == {}
    assert "frontmatter_error" not in r, r


def test_ap51_frontmatter_legible_sigue_igual(tmp_path):
    r = _leer(tmp_path, "---\ntitle: Nota\n---\n\ncuerpo\n")
    assert r["meta"] == {"title": "Nota"} and r["body"] == "cuerpo"
    assert "frontmatter_error" not in r, r
