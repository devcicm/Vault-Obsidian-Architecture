#!/usr/bin/env python3
"""Shared pytest fixtures for vault tests.

Run from repo root:
    python -m pytest tests/ -v
"""

import sys
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Ensure scripts/ is importable for all test modules
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def repo_root() -> Path:
    """Path to the repository root."""
    return REPO_ROOT


@pytest.fixture
def scripts_dir() -> Path:
    """Path to the scripts/ directory."""
    return SCRIPTS_DIR


@pytest.fixture
def tmp_test_dir(tmp_path) -> Path:
    """Isolated temp dir for write tests (no pollution of real vault)."""
    test_dir = tmp_path / "vault_test"
    test_dir.mkdir()
    return test_dir


@pytest.fixture
def sample_note(tmp_test_dir) -> Path:
    """Create a sample .md note in the temp test dir."""
    note = tmp_test_dir / "sample-note.md"
    note.write_text(
        "---\n"
        "title: Sample\n"
        "id: test-sample-001\n"
        "createdAt: 2026-06-27T00:00:00.000Z\n"
        "updatedAt: 2026-06-27T00:00:00.000Z\n"
        "agent: test\n"
        "---\n\n"
        "# Sample\n\nContent here.\n",
        encoding="utf-8",
    )
    return note
