"""The change log is the single record of a move (bigo-inmutabilidad, S8 b).

Until 2026-11-19 `vault_move` wrote every move twice: a record in
`00_System/move-log.json` (Grafo) and a `moved` row in the change log. The row
now carries the instant of the move (`moved_at`, at the precision the record
had) and `move-log.json` is frozen: never written again, still read first by
the log's owner, so `vault_graph` (moved nodes) and `vault_audit` (`moved_node`
actions) keep reading a vault from before. Older `moved` rows, written next to
a record, carry no `moved_at` and are not counted twice.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Tuple

import pytest

from apoyo import correr_tool, escribir_nota, filas_de_bitacora

_A = "07_Knowledge/00-07_knowledge-primer.md"
_B = "07_Knowledge/primer-movido.md"
_C = "05_Patterns/00-05_patterns-primer.md"
_D = "05_Patterns/primer-movido.md"


@pytest.fixture(scope="module")
def _vault_base(tmp_path_factory) -> Path:
    raiz = tmp_path_factory.mktemp("movimientos") / "vault"
    raiz.mkdir()
    r = correr_tool("vault_init", "--no-audit", "--no-git", vault=raiz)
    assert r.codigo == 0, r.stdout + r.stderr
    return raiz


@pytest.fixture
def vault(_vault_base, tmp_path) -> Path:
    copia = tmp_path / "vault"
    shutil.copytree(_vault_base, copia)
    return copia


def _mover(vault: Path, origen: str, destino: str) -> dict:
    r = correr_tool("vault_move", "--from", origen, "--to", destino, "--json", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    return r.envelope


def _movidas(vault: Path) -> List[Tuple[str, str]]:
    informe = correr_tool("vault_audit", vault=vault).envelope
    assert informe["ok"], informe
    return [(a["from"], a["to"]) for a in informe["nextActions"]
            if a.get("category") == "moved_node"]


def _envejecer_grafo(vault: Path) -> None:
    grafo = vault / "99_Index" / "graph.json"
    os.utime(grafo, (grafo.stat().st_atime, grafo.stat().st_mtime - 3600))


def _nodos(vault: Path) -> dict:
    r = correr_tool("vault_graph", vault=vault)
    assert r.envelope["ok"], r.envelope
    return json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))["nodes"]


def _filas_movidas(vault: Path) -> list:
    return [f for f in filas_de_bitacora(vault) if f["action"] == "moved"]


def test_un_movimiento_nuevo_queda_solo_en_el_change_log(vault):
    envelope = _mover(vault, _A, _B)

    assert not (vault / "00_System" / "move-log.json").exists()
    filas = _filas_movidas(vault)
    assert len(filas) == 1, filas
    fila = filas[0]
    assert (fila["path"], fila["new_path"], fila["agent"]) == (_A, _B, "vault_move")
    assert fila["moved_at"] == envelope["record"]["timestamp"]
    assert envelope["change_log"] == {"id": fila["id"], "action": "moved"}
    assert envelope["degraded"] == []
    # The record in the envelope keeps its shape.
    assert set(envelope["record"]) == {"from", "to", "timestamp", "links_updated",
                                       "files_checked", "dry_run"}
    md = (vault / "00_System" / "change-log.md").read_text(encoding="utf-8")
    assert f"| `moved` | `{_A}` | `{_B}` |" in md


def test_el_grafo_marca_el_nodo_movido_desde_el_change_log(vault):
    envelope = _mover(vault, _A, _B)
    # A note at the old path again: the graph marks the node it finds there.
    escribir_nota(vault, _A, {"title": "Otra", "status": "draft", "agent": "pytest"},
                  "# Otra\n\nUna nota nueva en la ruta de la que se movio la otra.\n")

    nodos = _nodos(vault)
    assert not (vault / "00_System" / "move-log.json").exists()
    assert nodos[_A]["status"] == "moved"
    assert nodos[_A]["moved_to"] == _B
    assert nodos[_A]["moved_at"] == envelope["record"]["timestamp"]


def test_el_audit_pide_el_grafo_solo_si_es_anterior_a_cada_movimiento(vault):
    _mover(vault, _A, _B)
    assert _movidas(vault) == []
    # The second move too: its log already exists, so nothing refreshes the
    # graph after the move but the move itself (QA-FL-08 echoed it until
    # 2026-11-19, the instant was taken after the move refreshed the graph).
    _mover(vault, _C, _D)
    assert _movidas(vault) == []

    _envejecer_grafo(vault)
    assert _movidas(vault) == [(_A, _B), (_C, _D)]
    assert correr_tool("vault_graph", vault=vault).envelope["ok"]
    assert _movidas(vault) == []


def test_el_move_log_congelado_se_sigue_leyendo_y_no_se_escribe(vault):
    """A vault from before: its record and the `moved` row written next to it."""
    viejo = "07_Knowledge/destino-de-antes.md"
    congelado = vault / "00_System" / "move-log.json"
    congelado.write_bytes(json.dumps([{"from": _A, "to": viejo}], indent=2).encode("utf-8"))
    r = correr_tool("vault_change_log", "--action", "moved", "--path", _A, "--new_path", viejo,
                    "--reason", "moved by vault_move", vault=vault)
    assert r.envelope["ok"], r.envelope
    antes = congelado.read_bytes()

    nodos = _nodos(vault)
    assert (nodos[_A]["status"], nodos[_A]["moved_to"], nodos[_A]["moved_at"]) == (
        "moved", viejo, None)
    # Once, from the frozen record: the row without `moved_at` is that record.
    assert _movidas(vault) == [(_A, viejo)]

    _mover(vault, _C, _D)
    assert congelado.read_bytes() == antes
    _envejecer_grafo(vault)
    assert _movidas(vault) == [(_A, viejo), (_C, _D)]


def test_el_instante_del_movimiento_se_valida(vault):
    import vault_io
    from vault_change_log import vault_change_log_add

    vault_io.set_vault_root(vault)
    antes = filas_de_bitacora(vault)
    malo = vault_change_log_add("moved", _A, "x", new_path=_B, moved_at="ayer")
    assert (malo["ok"], malo["error_code"]) == (False, "INVALID_VALUE")
    sin_mover = vault_change_log_add("created", _A, "x",
                                     moved_at="2026-11-19T00:00:00+00:00")
    assert (sin_mover["ok"], sin_mover["error_code"]) == (False, "INVALID_VALUE")
    assert filas_de_bitacora(vault) == antes
