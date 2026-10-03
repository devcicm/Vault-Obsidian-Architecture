"""vault_fix_brackets --path no confunde «no pude mirar» con «no hay nada» (AP-51).

Medido 2026-10-02: una ruta fuera del vault (`../x.md`, absoluta) o una que no
existe devolvían `ok: true, scanned: 0, findings_total: 0`, idéntico a un
vault sin corchetes rotos. El agente que lo pedía daba la nota por sana.
La contención sí se cumplía: nunca leyó fuera.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

ROTA = "---\ntitle: n\n---\nver [[]] aquí\n"


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "07_Knowledge").mkdir()
    (root / "07_Knowledge" / "n.md").write_text(ROTA, encoding="utf-8")
    (tmp_path / "fuera.md").write_text(ROTA, encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


@pytest.mark.parametrize("ruta", ["../fuera.md", "ABS"])
def test_ap51_ruta_fuera_del_vault_es_un_error(vault, ruta):
    import vault_fix_brackets

    if ruta == "ABS":
        ruta = str(vault.parent / "fuera.md")
    r = vault_fix_brackets.vault_fix_brackets(path=ruta, apply=True)
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"
    assert (vault.parent / "fuera.md").read_text(encoding="utf-8") == ROTA


def test_ap51_ruta_inexistente_es_un_error(vault):
    import vault_fix_brackets

    r = vault_fix_brackets.vault_fix_brackets(path="07_Knowledge/no-existe.md")
    assert r["ok"] is False and r["error_code"] == "FILE_NOT_FOUND"


def test_ruta_valida_sigue_encontrando(vault):
    import vault_fix_brackets

    r = vault_fix_brackets.vault_fix_brackets(path="07_Knowledge/n.md")
    assert r["ok"] is True and r["scanned"] == 1 and r["findings_total"] == 1
