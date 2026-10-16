"""AP-51 — una nota que no se pudo leer no se puntúa como nota sin frontmatter.

`_read_frontmatter_raw` capturaba `Exception` y devolvía `({}, "")`: la nota
ilegible salía puntuada como vacía, sin frontmatter, y el índice de calidad
culpaba al dato del fallo de la tool. Ahora sale aparte, en `notes_unreadable`,
y no entra en la media.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_quality_check as q  # noqa: E402

NOTA = """---
title: "Nota {n}"
type: knowledge
status: active
tags: [prueba]
created: 2026-10-16
---

# Nota {n}

Contenido suficiente para que la nota tenga cuerpo.
"""


def test_la_nota_ilegible_sale_aparte_y_no_puntua(tmp_path, monkeypatch):
    vault = tmp_path / "v"
    (vault / "00_System").mkdir(parents=True)
    (vault / "07_Knowledge").mkdir()
    for n in ("a", "b"):
        (vault / "07_Knowledge" / f"{n}.md").write_text(NOTA.format(n=n), encoding="utf-8")

    original = Path.read_text

    def lectura(self, *a, **k):
        if self.name == "b.md":
            raise PermissionError("bloqueada")
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", lectura)
    vault_io.set_vault_root(vault)
    r = q.vault_quality_check(check_only=True)

    assert r["ok"] is True
    assert r["notes_unreadable"] == [{"path": "07_Knowledge/b.md", "error": "PermissionError"}]
    assert "07_Knowledge/b.md" not in r["notes"]
    assert r["total_notes"] == 1
