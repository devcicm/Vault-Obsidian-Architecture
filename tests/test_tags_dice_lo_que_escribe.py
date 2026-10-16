"""`vault_tags` dice cuánto escribió, medido y no declarado (AP-37).

Auditoría del 2026-10-15: `rebuild` y `rename` escriben el registro, el índice
y las notas, y devolvían `ok: true` sin `write_report()`. `vault_noop_audit`
no lo veía porque el contrato declara `total` y `renamed`, que ningún modo
emite: el audit mide lo **declarado**, no lo **emitido**. Lo primero se arregla
aquí; lo segundo queda como deuda `ap37_mide_lo_declarado`.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_io  # noqa: E402
import vault_tags  # noqa: E402
from vault.kernel import ledger  # noqa: E402


#: La raíz del repo, para lo que se mide contra él y no contra el vault temporal.
_ORIGINAL = {}


@pytest.fixture
def vault(tmp_path):
    original = vault_io.get_vault_root()
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\ntype: knowledge\ntags: [\"config\", \"api\"]\n---\n\n"
        "Cuerpo con contenido suficiente.\n",
        encoding="utf-8",
    )
    _ORIGINAL["raiz"] = original
    vault_io.set_vault_root(raiz)
    ledger.write_ledger_reset()
    yield raiz
    vault_io.set_vault_root(original)


def _bytes(raiz):
    return {p: p.read_bytes() for p in raiz.rglob("*") if p.is_file()}


def test_ap37_rebuild_dice_lo_que_escribio(vault):
    r = vault_tags.vault_tags_rebuild()
    assert r["written"] == 2, r  # registro e índice, los dos nuevos
    # Lo que dice es lo que cambió en disco, medido por bytes y no por la tool.
    antes = _bytes(vault)
    ledger.write_ledger_reset()
    r = vault_tags.vault_tags_rebuild()
    despues = _bytes(vault)
    assert r["written"] == sum(antes.get(p) != b for p, b in despues.items()), r


def test_el_indice_de_tags_no_se_indexa_a_si_mismo(vault):
    """Auditoría del 2026-10-15: el segundo `rebuild` listaba `tag-index.md`
    —que escribió el primero— como nota sin tags, y la cifra cambiaba de una
    ejecución a otra sin que cambiara el vault.
    """
    indice = vault / "99_Index" / "tag-index.md"
    vault_tags.vault_tags_rebuild()
    primero = indice.read_text(encoding="utf-8").split("---", 2)[2]
    r = vault_tags.vault_tags_rebuild()
    assert "99_Index/tag-index.md" not in r.get("untagged", []), r
    assert indice.read_text(encoding="utf-8").split("---", 2)[2] == primero


def test_ap37_rename_dice_lo_que_escribio(vault):
    r = vault_tags.vault_tags_rename("config", "ajustes")
    assert r["written"] >= 1, r
    ledger.write_ledger_reset()
    r = vault_tags.vault_tags_rename("config", "ajustes")
    assert r["written"] == 0, r


def test_limite_declarado_ap37_mide_lo_declarado(vault):
    """El audit da por bueno un indicador que el contrato declara y nadie emite.

    Falla el día que `vault_noop_audit` contraste lo declarado con lo emitido
    —o que el contrato de `vault_tags` deje de prometer `total`—; entonces la
    deuda se salda.
    """
    import vault_blueprint
    import vault_noop_audit

    deuda = {d["id"]: d for d in vault_blueprint.DEUDA_DECLARADA}["ap37_mide_lo_declarado"]
    assert deuda["estado"] == "pendiente"
    vault_io.set_vault_root(_ORIGINAL["raiz"])  # el contrato vive en el repo
    try:
        ofensores = {o["tool"] for o in vault_noop_audit.offenders()}
    finally:
        vault_io.set_vault_root(vault)
    assert "vault_tags" not in ofensores
    emitidos = set(vault_tags.vault_tags_rebuild()) | set(vault_tags.vault_tags_rename("api", "x"))
    assert "total" not in emitidos
