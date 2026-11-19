#!/usr/bin/env python3
"""Concurrency test for vault_change_log — no lost entries under parallel writers.

Run from repo root:
    python -m pytest tests/test_vault_changelog_concurrency.py -v

vault_change_log_add appends one line to .change-log.jsonl under file_lock
(append-only since bigo-inmutabilidad). Before the file_lock fix, the old
read-append-write of .change-log.json let two processes read the same log,
each append, and the second write clobbered the first (lost entry). This test
drives many concurrent adds and asserts every entry survives, whole.
"""

import os
import json
import threading
from pathlib import Path


import vault_change_log as cl


def test_same_requirement_event_is_idempotent_across_processes(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from apoyo import correr_python

    root = tmp_path / "vault"
    (root / "00_System").mkdir(parents=True)
    code = """
import json
from vault_change_log import vault_change_log_add
result = vault_change_log_add(action="transition", path="14_Requirements/demo/req-001.md",
    reason="Create requirement", agent="test", event_id="40546746-302c-450e-a080-30a455674ff6",
    requirement={"project": "demo", "req_id": "REQ-001", "from": None, "to": "draft"})
print(json.dumps(result))
"""

    def run(_):
        return correr_python("-c", code, vault=root)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, range(3)))
    assert all(result.returncode == 0 and json.loads(result.stdout)["ok"] for result in results)
    import vault_io

    vault_io.set_vault_root(root)
    rows = cl.leer_historial_completo()
    assert len(rows) == 1
    markdown = (root / "00_System" / "change-log.md").read_text(encoding="utf-8")
    assert markdown.count("requirement-event:40546746-302c-450e-a080-30a455674ff6") == 1


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

    lectura = cl.leer_bitacora()
    assert lectura.lineas_rotas == (), "an append left a torn line"
    entries = lectura.entradas
    assert len(entries) == n, f"Lost updates: {len(entries)} of {n} entries recorded"
    # Every writer's unique path is present exactly once.
    paths = {e["path"] for e in entries}
    assert paths == {f"07_Knowledge/note-{i}.md" for i in range(n)}
