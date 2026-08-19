#!/usr/bin/env python3
"""
Tests for vault_model_profile tool.

Run with: python -m pytest tests/test_vault_model_profile.py -v
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

from vault_model_profile import (
    MODEL_MAPPING,
    vault_model_profile_resolve,
    vault_model_profile_list,
    vault_model_profile_set,
    _resolve_profile,
    FLOOR_BUDGET,
)


class TestModelMapping:
    def test_claude_desktop_maps_to_claude(self):
        assert MODEL_MAPPING["claude-desktop"] == "claude"

    def test_cursor_maps_to_cursor(self):
        assert MODEL_MAPPING["cursor"] == "cursor"

    def test_gpt_maps_to_gpt4o(self):
        assert MODEL_MAPPING["openai-gpt"] == "gpt-4o"
        assert MODEL_MAPPING["Codex"] == "gpt-4o"

    def test_gemini_maps_to_gemini(self):
        assert MODEL_MAPPING["gemini-cli"] == "gemini"

    def test_deepseek_maps_to_deepseek(self):
        assert MODEL_MAPPING["deepseek-chat"] == "deepseek"


class TestVaultModelProfileResolve:
    def test_explicit_overrides_env(self):
        result = vault_model_profile_resolve(explicit="cursor", from_env="claude")
        assert result["profile_id"] == "cursor"
        assert result["source"] == "active"

    def test_env_overrides_auto(self):
        result = vault_model_profile_resolve(from_env="gemini", from_auto="claude-desktop")
        assert result["profile_id"] == "gemini"
        assert result["source"] == "env"

    def test_auto_maps_known_client(self):
        result = vault_model_profile_resolve(from_auto="claude-desktop")
        assert result["profile_id"] == "claude"
        assert result["source"] == "auto"

    def test_auto_unknown_client_returns_default(self):
        result = vault_model_profile_resolve(from_auto="unknown-vendor-xyz")
        assert result["profile_id"] == "claude"
        assert result["source"] == "default"

    def test_unknown_profile_returns_floor_budget(self, monkeypatch):
        monkeypatch.setattr(
            "vault_model_profile._load_registry",
            lambda: {"claude": {"context_window": 200000, "budget": 15000, "supports_mcp": True}},
        )
        result = vault_model_profile_resolve(explicit="nonexistent")
        assert result["budget"] == FLOOR_BUDGET
        assert result["context_window"] == FLOOR_BUDGET
        assert "warning" in result


class TestVaultModelProfileList:
    def test_list_returns_profiles(self):
        result = vault_model_profile_list()
        assert result["ok"] is True
        assert "profiles" in result
        assert len(result["profiles"]) >= 5
        ids = [p["id"] for p in result["profiles"]]
        assert "claude" in ids
        assert "gpt-4o" in ids
        assert "gemini" in ids

    def test_active_is_marked(self):
        result = vault_model_profile_list()
        active_profiles = [p for p in result["profiles"] if p["active"]]
        assert len(active_profiles) == 1


class TestVaultModelProfileSet:
    def test_set_invalid_profile_returns_error(self, monkeypatch):
        monkeypatch.setattr(
            "vault_model_profile._load_registry",
            lambda: {"claude": {"context_window": 200000, "budget": 15000, "supports_mcp": True}},
        )
        result = vault_model_profile_set("invalid-profile")
        assert result["ok"] is False
        assert result["error_code"] == "MODEL_PROFILE_UNKNOWN"


class TestCLIModes:
    def test_list_flag(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_model_profile.py"), "--list"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert len(data["profiles"]) >= 5

    def test_budget_flag_prints_budget(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_model_profile.py"), "--budget"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0
        lines = r.stdout.strip().splitlines()
        assert lines[0].strip().isdigit()
        budget = int(lines[0].strip())
        assert budget >= FLOOR_BUDGET

    def test_window_flag_prints_context_window(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_model_profile.py"), "--window"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0
        val = int(r.stdout.strip())
        assert val > 0

    def test_auto_claude_desktop_maps_to_claude(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_model_profile.py"), "--auto", "claude-desktop"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["profile_id"] == "claude"
        assert data["source"] == "auto"

    def test_set_and_active_workflow(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_model_profile.py"), "--set", "gpt-4o"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["profile_id"] == "gpt-4o"

        r2 = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_model_profile.py"), "--active"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        assert r2.returncode == 0
        data2 = json.loads(r2.stdout)
        assert data2["profile_id"] == "gpt-4o"
