"""QA-RO-02 — one declaration of the ambient observability files (AP-57).

Two lists of "files every tool rewrites" had diverged: the snapshot hash
(`vault.durabilidad.snapshot.VOLATILES`) excluded the error trace and the voice
counter, while the write ledger (`vault.kernel.ledger._NO_ES_TRABAJO`) —and
through it the before/after trees of `vault_smoke` and `vault_toolkit_audit`—
excluded only the trace. Every voiced envelope advances
`00_System/.voice-counter`, so a read-only tool such as `vault_context_pack`
looked like a writer to the AP-37 bench.

The kernel declares the set once; every reader derives from it. The snapshot
rule keeps its meaning (`MERKLE_ALGO` 2 excludes exactly the same two files),
so existing manifests stay verifiable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import vault_smoke
import vault_toolkit_audit
from apoyo import correr_tool, entorno
from vault.durabilidad import snapshot
from vault.kernel import ledger

#: The set `MERKLE_ALGO` 2 has excluded since it was introduced. Changing it
#: would change the hash of every existing manifest.
EXCLUIDOS_POR_ALGO_2 = frozenset({"00_System/.tool-trace.json", "00_System/.voice-counter"})


def test_the_kernel_declaration_feeds_every_reader():
    declarados = ledger.FICHEROS_AMBIENTALES
    assert declarados == EXCLUIDOS_POR_ALGO_2
    assert snapshot.MERKLE_ALGO == 2
    assert snapshot.VOLATILES == declarados
    assert ledger._NO_ES_TRABAJO == frozenset(Path(r).name for r in declarados)


def test_the_ledger_does_not_count_an_ambient_file_as_work(tmp_path):
    ledger.write_ledger_reset()
    for relativa in sorted(ledger.FICHEROS_AMBIENTALES):
        assert ledger.record_raw_write(tmp_path / relativa, "1") == "unchanged"
    assert ledger.write_report()["written"] == 0
    # Previous behavior: any other file is still work.
    assert ledger.record_raw_write(tmp_path / "00_System" / "otro.json", "{}") == "created"
    assert ledger.write_report()["written"] == 1
    ledger.write_ledger_reset()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    return raiz


def _todo(raiz: Path) -> dict:
    return {p.relative_to(raiz).as_posix(): p.read_bytes()
            for p in raiz.rglob("*") if p.is_file()}


def test_a_voiced_read_only_tool_does_not_look_like_work(vault):
    env = entorno(vault, VAULT_VOICE="1")
    argv = ("vault_context_pack", "que decidimos sobre el transporte MCP", "--budget", "200")
    primera = correr_tool(*argv, env=env)
    assert primera.codigo == 0, primera.envelope
    assert "vault_says" in primera.envelope, "the envelope is voiced"

    antes_todo = _todo(vault)
    antes_smoke = vault_smoke._arbol(vault)
    antes_audit = vault_toolkit_audit._arbol_local(vault)
    segunda = correr_tool(*argv, env=env)
    assert segunda.codigo == 0, segunda.envelope

    # The voice really advanced its counter on disk...
    despues_todo = _todo(vault)
    cambiados = {r for r in set(antes_todo) | set(despues_todo)
                 if antes_todo.get(r) != despues_todo.get(r)}
    assert "00_System/.voice-counter" in cambiados
    assert cambiados <= ledger.FICHEROS_AMBIENTALES, cambiados
    # ...and neither the AP-37 bench nor the toolkit audit counts it as work.
    assert vault_smoke._arbol(vault) == antes_smoke
    assert vault_toolkit_audit._arbol_local(vault) == antes_audit


def test_a_real_write_is_still_seen_by_the_trees(vault):
    """Previous behavior: a file outside the declaration changes the trees."""
    antes_smoke = vault_smoke._arbol(vault)
    antes_audit = vault_toolkit_audit._arbol_local(vault)
    (vault / "07_Knowledge").mkdir()
    (vault / "07_Knowledge" / "nota.md").write_text("cuerpo", encoding="utf-8")
    assert "07_Knowledge/nota.md" in set(vault_smoke._arbol(vault)) - set(antes_smoke)
    assert "07_Knowledge/nota.md" in set(vault_toolkit_audit._arbol_local(vault)) - set(antes_audit)
