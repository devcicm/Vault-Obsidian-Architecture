"""vault_move no cruza la frontera del vault en ninguna dirección (AP-36).

Medido 2026-10-02: `--from ../fuera.md` metía en el vault un fichero de fuera
y borraba el original; `--to ../x.md` y `--to-folder ../x` sacaban notas y
carpetas enteras; `--impact` leía un fichero de fuera. Todo con `ok: true`, y
por MCP, sobre cualquier ruta del disco del usuario.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

NOTA = "---\ntitle: n\n---\ncuerpo\n"


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "01_Projects" / "sub").mkdir(parents=True)
    (root / "01_Projects" / "n.md").write_text(NOTA, encoding="utf-8")
    (root / "01_Projects" / "sub" / "m.md").write_text(NOTA, encoding="utf-8")
    (tmp_path / "fuera.md").write_text(NOTA, encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def _fuera(vault):
    return sorted(p.name for p in vault.parent.iterdir() if p.name != "v")


def test_ap36_no_mete_en_el_vault_un_fichero_de_fuera(vault):
    import vault_move

    r = vault_move.move_note("../fuera.md", "01_Projects/x.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"
    assert (vault.parent / "fuera.md").is_file()
    assert not (vault / "01_Projects" / "x.md").exists()


def test_ap36_no_saca_una_nota_del_vault(vault):
    import vault_move

    r = vault_move.move_note("01_Projects/n.md", "../sacada.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"
    assert (vault / "01_Projects" / "n.md").is_file()
    assert _fuera(vault) == ["fuera.md"]


def test_ap36_no_saca_una_carpeta_del_vault(vault):
    import vault_move

    r = vault_move.move_folder("01_Projects/sub", "../carpeta")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"
    assert (vault / "01_Projects" / "sub" / "m.md").is_file()
    assert _fuera(vault) == ["fuera.md"]


def test_ap36_impact_no_lee_un_fichero_de_fuera(vault):
    import vault_move

    r = vault_move.check_move_impact("../fuera.md", "01_Projects/x.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"


def test_ap36_una_ruta_absoluta_tampoco_entra(vault):
    import vault_move

    r = vault_move.move_note(str(vault.parent / "fuera.md"), "01_Projects/x.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"
    assert (vault.parent / "fuera.md").is_file()


def test_un_movimiento_dentro_del_vault_sigue_funcionando(vault):
    import vault_move

    r = vault_move.move_note("01_Projects/n.md", "01_Projects/sub/n2.md")
    assert r["ok"] is True
    assert (vault / "01_Projects" / "sub" / "n2.md").is_file()
