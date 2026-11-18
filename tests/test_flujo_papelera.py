"""QA-FL-06 - the trash flow ends where it started, and the indexes follow the note.

Measured by the flow QA on a fresh vault (c09473ab): `vault_delete --trash-only`
moved the note to `20_Quarantine/` behind the quarantine owner's back, so
`vault_quarantine --list` counted 0, `--restore` answered `NOT_QUARANTINED`
and `vault_undo --restore` `NOTE_NOT_FOUND`; only an undocumented
`vault_move` brought it back. The trash removed the search row without adding
the quarantine path, so after moving back `vault_search` found nothing, and
`vault_quarantine --add/--restore` left the row of the path the note had left.

Each step is checked as the consumer sees it: `vault_reindex --check` exits 0
and `vault_search` returns the note at the path where it is on disk.
"""

import json
import shlex

import pytest

from apoyo import correr_en_proceso, correr_tool, escribir_nota

NOTA = "07_Knowledge/zebra-nota.md"
CUERPO = """
    # Zebra nota

    zebrafish appears only in this note, line one.
    A second line of real content for the note.
    A third line of real content for the note.
"""


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "08_Runbooks", "20_Quarantine", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    escribir_nota(raiz, NOTA, {"title": "Zebra nota", "type": "knowledge", "status": "draft",
                               "tags": ["demo"]}, CUERPO)
    # A lived-in vault already has its change log; the baseline indexes it.
    hecho = correr_en_proceso("vault_change_log", "--action", "created", "--path", NOTA,
                              "--reason", "fixture", vault=raiz, agente="pytest")
    assert hecho.codigo == 0, hecho.stdout[-800:]
    hecho = correr_en_proceso("vault_reindex", vault=raiz, agente="pytest")
    assert hecho.codigo == 0, hecho.stdout[-800:]
    return raiz


def _tool(vault, nombre, *argv):
    corrida = correr_en_proceso(nombre, *argv, vault=vault, agente="pytest")
    return corrida.codigo, corrida.envelope


def _encontradas(vault):
    codigo, env = _tool(vault, "vault_search", "--query", "zebrafish")
    assert codigo == 0, env
    return sorted(r["path"] for r in env["results"])


def _coherente(vault):
    """`vault_reindex --check` exits 0: disk and search index agree."""
    codigo, env = _tool(vault, "vault_reindex", "--check")
    assert codigo == 0 and env["status"] == "index_ok", {
        k: env.get(k) for k in ("status", "missing_in_index", "stale_in_index",
                                "modified_in_index")}


def _ledger(vault):
    fichero = vault / "20_Quarantine" / ".quarantine-ledger.json"
    return json.loads(fichero.read_text(encoding="utf-8"))["entries"]


def test_trash_only_queda_retenida_y_su_restauracion_la_devuelve(vault):
    _coherente(vault)
    codigo, env = _tool(vault, "vault_delete", "--path", NOTA, "--reason", "needs review",
                        "--trash-only")
    retenida = "20_Quarantine/unclassified/zebra-nota.md"
    assert codigo == 0 and env["ok"] is True, env
    assert env["action"] == "moved_to_quarantine" and env["trashed"] is True, env
    assert env["deleted"] is False and env["change_logged"] is True, env
    assert env["quarantined_to"] == retenida, env
    assert env["recoverable"]["restore"] == f'vault_quarantine --restore "{retenida}"', env
    assert not (vault / NOTA).exists() and (vault / retenida).is_file()
    assert [(e["origin"], e["path"], e["restored"]) for e in _ledger(vault)] == [
        (NOTA, retenida, False)]
    assert _encontradas(vault) == [retenida]
    _coherente(vault)

    codigo, env = _tool(vault, "vault_quarantine", "--list")
    assert codigo == 0 and env["count"] == 1, env
    assert env["entries"][0]["origin"] == NOTA, env

    # The recovery the envelope names, followed literally.
    orden = shlex.split(f'vault_quarantine --restore "{retenida}"')
    codigo, env = _tool(vault, orden[0], *orden[1:])
    assert codigo == 0 and env["ok"] is True and env["path"] == NOTA, env
    assert (vault / NOTA).is_file() and not (vault / retenida).exists()
    assert "quarantine_origin" not in (vault / NOTA).read_text(encoding="utf-8")
    assert _ledger(vault)[0]["restored"] is True
    assert _encontradas(vault) == [NOTA]
    _coherente(vault)


def test_quarantine_add_y_restore_mueven_la_fila_de_busqueda(vault):
    retenida = "20_Quarantine/suspicious/zebra-nota.md"
    codigo, env = _tool(vault, "vault_quarantine", "--add", NOTA, "--reason", "odd source",
                        "--category", "suspicious")
    assert codigo == 0 and env["path"] == retenida and env["origin"] == NOTA, env
    assert env["indexes"]["search_index"]["removed"] == 1, env
    assert env["indexes"]["degraded"] == [], env
    assert _encontradas(vault) == [retenida]
    _coherente(vault)

    codigo, env = _tool(vault, "vault_quarantine", "--restore", retenida)
    assert codigo == 0 and env["path"] == NOTA and env["from"] == retenida, env
    assert env["indexes"]["search_index"]["removed"] == 1, env
    assert _encontradas(vault) == [NOTA]
    _coherente(vault)


def test_mover_de_vuelta_desde_cuarentena_indexa_la_ruta_nueva(vault):
    retenida = "20_Quarantine/unclassified/zebra-nota.md"
    _tool(vault, "vault_quarantine", "--add", NOTA, "--reason", "parked")
    # The row of the quarantine path is gone before the move (the case the QA
    # measured after the old trash): the move must still index the new path.
    indice = vault / "99_Index" / "search-index.json"
    datos = json.loads(indice.read_text(encoding="utf-8"))
    datos["notes"] = [n for n in datos["notes"] if n["path"] != retenida]
    indice.write_text(json.dumps(datos), encoding="utf-8")

    codigo, env = _tool(vault, "vault_move", "--from", retenida, "--to", NOTA, "--json")
    assert codigo == 0 and env["ok"] is True, env
    assert env["search_index_updated"] is True and env["degraded"] == [], env
    assert _encontradas(vault) == [NOTA]


def test_reclasificar_al_mover_deja_una_sola_fila(vault):
    destino = "08_Runbooks/zebra-nota.md"
    codigo, env = _tool(vault, "vault_move", "--from", NOTA, "--to", destino,
                        "--type", "runbook", "--json")
    assert codigo == 0 and env["ok"] is True and env["degraded"] == [], env
    assert _encontradas(vault) == [destino]
    _coherente(vault)


def test_borrar_y_deshacer_sigue_funcionando(vault):
    codigo, env = _tool(vault, "vault_delete", "--path", NOTA, "--reason", "obsolete")
    assert codigo == 0 and env["action"] == "deleted" and env["deleted"] is True, env
    assert env["recoverable"]["restore"] == f'vault_undo --restore "{NOTA}"', env
    assert not (vault / NOTA).exists()
    assert _encontradas(vault) == []
    _coherente(vault)

    codigo, env = _tool(vault, "vault_undo", "--restore", NOTA)
    assert codigo == 0 and env["action"] == "restored_deleted", env
    assert (vault / NOTA).is_file()
    assert _encontradas(vault) == [NOTA]


def test_las_simulaciones_no_escriben(vault):
    indice = vault / "99_Index" / "search-index.json"
    antes = indice.read_bytes()
    codigo, env = _tool(vault, "vault_delete", "--path", NOTA, "--reason", "r",
                        "--trash-only", "--dry-run")
    assert codigo == 0 and env["would_move_to_quarantine"] is True, env
    assert env["trashed"] is False and env["change_logged"] is False, env
    codigo, env = _tool(vault, "vault_move", "--from", NOTA, "--to", "07_Knowledge/otra.md",
                        "--json", "--dry-run")
    assert codigo == 0 and env["search_index_updated"] is True, env
    assert (vault / NOTA).is_file()
    assert not (vault / "20_Quarantine" / ".quarantine-ledger.json").exists()
    assert indice.read_bytes() == antes


def test_la_cli_de_la_papelera_publica_la_restauracion(vault):
    """The CLI contract, once by subprocess: the published script prints the envelope."""
    corrida = correr_tool("vault_delete", "--path", NOTA, "--reason", "r", "--trash-only",
                          vault=vault)
    assert corrida.codigo == 0, corrida.stderr[-800:]
    assert corrida.envelope["recoverable"]["restore"].startswith("vault_quarantine --restore")
