#!/usr/bin/env python3
"""Tests for vault_io safety-critical primitives.

Run from repo root:
    python -m pytest tests/test_vault_io.py -v

These tests cover the B1 fix (atomic_write_text temp leak) and basic
file_lock behavior. They MUST pass before any release.
"""

import sys
import os
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from vault_io import atomic_write_text, file_lock


class TestAtomicWriteText:
    """Tests for atomic_write_text — B1 fix verification."""

    def test_successful_write_creates_file(self, tmp_test_dir):
        """Normal write succeeds and creates the target file."""
        target = tmp_test_dir / "note.md"
        atomic_write_text(target, "hello world")
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_failure_does_not_leak_temp_file(self, tmp_test_dir):
        """When write_text fails, no .tmp.* orphan remains."""
        target = tmp_test_dir / "fail.md"
        # Pass None — sanitize_content will raise TypeError on .strip() etc.
        with pytest.raises(Exception):
            atomic_write_text(target, None)
        # Verify no leak
        leaked = list(tmp_test_dir.glob(".tmp.*"))
        assert leaked == [], f"Temp files leaked: {leaked}"

    def test_overwrite_existing_file(self, tmp_test_dir):
        """Overwriting an existing file works atomically."""
        target = tmp_test_dir / "note.md"
        atomic_write_text(target, "first")
        atomic_write_text(target, "second")
        assert target.read_text(encoding="utf-8") == "second"

    def test_creates_parent_dirs(self, tmp_test_dir):
        """Missing parent directories are created automatically."""
        target = tmp_test_dir / "subdir" / "nested" / "note.md"
        atomic_write_text(target, "deep")
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "deep"


class TestFileLock:
    """Tests for file_lock — concurrent write safety."""

    def test_lock_acquire_and_release(self, tmp_test_dir):
        """Lock can be acquired and released without errors."""
        target = tmp_test_dir / "locked.txt"
        with file_lock(target, timeout=5):
            assert (target.parent / ".locks").exists()

    def test_concurrent_locks_serialize(self, tmp_test_dir):
        """Two writers under file_lock do not lose data."""
        import threading

        target = tmp_test_dir / "concurrent.json"
        results = []

        def writer(n: int):
            with file_lock(target, timeout=10):
                import json

                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError):
                    existing = []
                existing.append({"writer": n, "ts": "2026-06-27T00:00:00Z"})
                target.write_text(
                    json.dumps(existing, ensure_ascii=False), encoding="utf-8"
                )
                results.append(n)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        import json

        data = json.loads(target.read_text(encoding="utf-8"))
        assert len(data) == 10, f"Lost updates: only {len(data)} of 10 writers recorded"

    def test_lock_timeout_raises(self, tmp_test_dir):
        """Pedir un lock que sostiene OTRO hilo con timeout=0 levanta TimeoutError.

        Desde v40.7 el lock es reentrante por hilo, así que la versión anterior
        de este test —que lo pedía dos veces desde el mismo hilo— ya no mide un
        timeout: mide la reentrancia, que tiene sus propios tests en
        `test_lock_reentrante.py`. El caso que este test debe seguir cubriendo
        es la contención real, y esa es entre hilos distintos.
        """
        target = tmp_test_dir / "timeout.txt"
        fallo = []

        def intruso():
            try:
                with file_lock(target, timeout=0):
                    fallo.append("entró")
            except TimeoutError:
                fallo.append("timeout")

        with file_lock(target, timeout=0):
            t = threading.Thread(target=intruso)
            t.start()
            t.join(timeout=10)

        assert fallo == ["timeout"], fallo
