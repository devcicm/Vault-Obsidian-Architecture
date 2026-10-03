"""vault_project_status conserva la identidad de la nota que actualiza (AP-44).

Releía `id` y `createdAt` partiendo líneas por `:` en vez de con YAML:
`id: 'x' # copiado` volvía como `x' # copiado` y la nota cambiaba de
identidad en la primera actualización (medido 2026-10-02).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from vault_lib import parse_frontmatter  # noqa: E402

ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def proyecto(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "01_Projects" / "alfa").mkdir(parents=True)
    vault_io.set_vault_root(root)
    return root / "01_Projects" / "alfa"


def test_ap44_un_comentario_yaml_no_cambia_la_identidad(proyecto):
    import vault_project_status

    (proyecto / "status.md").write_text(
        f"---\nid: '{ID}' # copiado\n"
        "createdAt: 2026-01-01T00:00:00.000Z # migrado\n---\nviejo\n", encoding="utf-8")
    r = vault_project_status.vault_project_status("alfa", "en_desarrollo", "hecho")
    assert r["ok"]
    fm = parse_frontmatter((proyecto / "status.md").read_text(encoding="utf-8"))
    assert fm["id"] == ID
    # El dueño normaliza el instante; lo que se conserva es el instante.
    assert fm["createdAt"] == "2026-01-01T00:00:00+00:00"
