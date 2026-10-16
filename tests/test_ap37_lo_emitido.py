"""AP-37 con el criterio del consumidor: lo que la tool escribe, lo dice.

Medido el 2026-10-16 ejecutando el ejemplo documentado de las 92 tools con
side effects sobre una copia del sandbox y comparando el árbol antes y
después: 17 escribían algo más que la traza, y dos lo callaban aunque su
contrato declarase el indicador —`vault_delta --snapshot` (declara
`added`/`changed`/`deleted`, ese camino no emite ninguno) y `vault_graph_fix
--apply` (declara `fixes_applied`, lo dejaba dentro de `apply_result`)—. Es la
deuda `ap37_mide_lo_declarado` vista en dos sitios concretos.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "scripts"), str(RAIZ)]

import vault_io  # noqa: E402
from vault.kernel import ledger  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    original = vault_io.get_vault_root()
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "99_Index").mkdir()
    (raiz / "07_Knowledge").mkdir()
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\ntype: knowledge\n---\n\nCuerpo con contenido suficiente.\n",
        encoding="utf-8")
    vault_io.set_vault_root(raiz)
    ledger.write_ledger_reset()
    yield raiz
    vault_io.set_vault_root(original)


def test_ap37_delta_snapshot_dice_lo_que_escribio(vault):
    import vault_delta

    r = vault_delta.vault_delta(snapshot_only=True)
    assert (vault / "99_Index" / "hash-index.json").is_file()
    assert r["written"] == 1 and r["created"] == 1, r
    ledger.write_ledger_reset()
    r = vault_delta.vault_delta(snapshot_only=True, dry_run=True)
    assert r["written"] == 0, r


def test_ap37_delta_dice_que_reescribio_el_indice(vault):
    import vault_delta

    vault_delta.vault_delta(snapshot_only=True)
    (vault / "07_Knowledge" / "otra.md").write_text(
        "---\ntitle: Otra\ntype: knowledge\n---\n\nOtro cuerpo.\n", encoding="utf-8")
    ledger.write_ledger_reset()
    r = vault_delta.vault_delta()
    assert r["added"] and r["updated"] == 1 and r["written"] == 1, r
