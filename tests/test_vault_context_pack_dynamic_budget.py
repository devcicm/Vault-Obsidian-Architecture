#!/usr/bin/env python3
"""
Tests for vault_context_pack dynamic budget from model profile.

Run with: python -m pytest tests/test_vault_context_pack_dynamic_budget.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


class TestContextPackDynamicBudget:
    def test_explicit_budget_overrides_profile(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_context_pack.py"),
             "arquitectura", "--budget", "500"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=60,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["tokens"]["budget"] == 500

    def test_profile_budget_used_when_no_explicit(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_context_pack.py"),
             "arquitectura"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=60,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["tokens"]["budget"] >= 2000

    def test_env_var_overrides_active_profile(self):
        env = {**os.environ, "VAULT_MODEL_PROFILE": "gemini"}
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_context_pack.py"),
             "arquitectura"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=60, env=env,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["tokens"]["budget"] == 4000
