"""vault_init cuenta lo que escribe (AP-36, AP-37).

Los primers se escribían con `Path.write_text`: sin temp+replace, sin escaneo
de secretos y fuera del ledger, así que no contaban como trabajo.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture
def vacio(tmp_path):
    import vault_io

    root = tmp_path / "v"
    root.mkdir()
    vault_io.set_vault_root(root)
    vault_io.write_ledger_reset()
    return root


def test_ap36_un_primer_pasa_por_la_escritura_atomica(vacio):
    import vault_init
    import vault_io

    r = vault_init._create_scaffold_note("01_Projects")
    assert r["created"] and (vacio / r["path"]).is_file()
    # >= y no ==: la escritura atómica arrastra el índice de la sección y el
    # hub, que vault_init generaría igualmente después.
    assert vault_io.write_report()["created"] >= 1
