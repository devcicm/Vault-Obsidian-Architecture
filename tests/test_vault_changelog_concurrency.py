#!/usr/bin/env python3
"""Concurrency test for vault_change_log — no lost entries under parallel writers.

Run from repo root:
    python -m pytest tests/test_vault_changelog_concurrency.py -v

vault_change_log_add does a read-append-write of .change-log.json. Before the
file_lock fix, two processes could read the same log, each append, and the
second write would clobber the first (lost entry). This test drives many
concurrent adds and asserts every entry survives.
"""

import sys
import os
import json
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import vault_change_log as cl


def _point_module_at(tmp: Path):
    """Se apunta la raíz del proceso, no las constantes del módulo.

    Las cuatro asignaciones que había aquí dejaron de existir al migrar
    `vault_change_log` al contexto Autoría. Seguirían siendo Python legal y no
    tendrían ningún efecto: este test habría lanzado 25 escrituras concurrentes
    contra el change-log **real de `vault-sandbox/`** y habría pasado en verde
    midiendo el vault equivocado. El override lo deshace el fixture autouse de
    `conftest.py`.
    """
    import vault_io

    (tmp / "00_System").mkdir(parents=True, exist_ok=True)
    vault_io.set_vault_root(tmp)


def test_concurrent_change_log_no_lost_entries(tmp_test_dir):
    _point_module_at(tmp_test_dir)
    n = 25

    def writer(i: int):
        cl.vault_change_log_add(
            action="updated",
            path=f"07_Knowledge/note-{i}.md",
            reason=f"concurrent write {i}",
            agent="claude",
        )

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entries = json.loads(cl._log_json().read_text(encoding="utf-8"))
    assert len(entries) == n, f"Lost updates: {len(entries)} of {n} entries recorded"
    # Every writer's unique path is present exactly once.
    paths = {e["path"] for e in entries}
    assert paths == {f"07_Knowledge/note-{i}.md" for i in range(n)}
