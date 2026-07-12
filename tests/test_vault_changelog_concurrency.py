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
    system = tmp / "00_System"
    system.mkdir(parents=True, exist_ok=True)
    cl.VAULT_ROOT = tmp  # so relative_to(VAULT_ROOT) in the response resolves
    cl.SYSTEM_DIR = system
    cl.LOG_MD = system / "change-log.md"
    cl.LOG_JSON = system / ".change-log.json"


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

    entries = json.loads(cl.LOG_JSON.read_text(encoding="utf-8"))
    assert len(entries) == n, f"Lost updates: {len(entries)} of {n} entries recorded"
    # Every writer's unique path is present exactly once.
    paths = {e["path"] for e in entries}
    assert paths == {f"07_Knowledge/note-{i}.md" for i in range(n)}
