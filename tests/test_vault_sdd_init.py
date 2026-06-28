#!/usr/bin/env python3
"""Tests for vault_sdd_init skill.

Run from repo root:
    python -m pytest tests/test_vault_sdd_init.py -v
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from vault_sdd_init import (
    EXPECTED_OUTPUTS,
    GENERATORS,
    detect_drift,
    generate_integrity_report,
    generate_readme,
    main,
)


class TestExpectedOutputs:
    """Tests for the expected output file list."""

    def test_has_14_expected_outputs(self):
        """Skill must generate 14 files."""
        assert len(EXPECTED_OUTPUTS) == 14

    def test_includes_readme(self):
        """README.md is always included."""
        assert "README.md" in EXPECTED_OUTPUTS

    def test_includes_principles(self):
        """00-principles.md is the first content doc."""
        assert "00-principles.md" in EXPECTED_OUTPUTS

    def test_includes_integrity_report(self):
        """integrity-report.json is generated."""
        assert "integrity-report.json" in EXPECTED_OUTPUTS

    def test_includes_gaps(self):
        """gaps.md is generated."""
        assert "gaps.md" in EXPECTED_OUTPUTS


class TestGenerators:
    """Tests for individual generators."""

    def test_all_generators_return_string(self, tmp_test_dir):
        """Every generator returns a non-empty string."""
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        for fname, gen in GENERATORS.items():
            content = gen(tmp_test_dir, drift)
            assert isinstance(content, str)
            assert len(content) > 0, f"{fname} returned empty content"

    def test_principles_is_bilingual(self, tmp_test_dir):
        """Principles doc has both ES and EN sections."""
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        content = GENERATORS["00-principles.md"](tmp_test_dir, drift)
        assert "## ES" in content
        assert "## EN" in content

    def test_antipatterns_includes_all_aps(self, tmp_test_dir):
        """Antipatterns doc includes AP-01..AP-25."""
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        content = GENERATORS["04-antipatterns.md"](tmp_test_dir, drift)
        for i in range(1, 26):
            assert f"AP-{i:02d}" in content, f"AP-{i:02d} missing from antipatterns doc"


class TestDetectDrift:
    """Tests for drift detection."""

    def test_returns_dict_with_required_keys(self):
        """Drift detection returns expected structure."""
        drift = detect_drift(Path("."))
        assert "version" in drift
        assert "missing_norms" in drift
        assert "warnings" in drift

    def test_no_missing_norms_in_v36(self):
        """With AP-01..AP-25 registered, no norms should be missing."""
        drift = detect_drift(Path("."))
        assert drift["missing_norms"] == [], f"Missing norms: {drift['missing_norms']}"


class TestIntegrityReport:
    """Tests for integrity report generation."""

    def test_report_has_required_fields(self, tmp_test_dir):
        """Integrity report contains all required fields."""
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        generated = ["README.md", "00-principles.md"]
        report = generate_integrity_report(tmp_test_dir, drift, generated)
        assert "ok" in report
        assert "vault_version" in report
        assert "generated_at" in report
        assert "expected_files" in report
        assert "missing_files" in report

    def test_missing_files_detected(self, tmp_test_dir):
        """Integrity report lists files that were not generated."""
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        generated = ["README.md"]
        report = generate_integrity_report(tmp_test_dir, drift, generated)
        missing = report["missing_files"]
        assert len(missing) == len(EXPECTED_OUTPUTS) - 1
        assert "00-principles.md" in missing

    def test_checks_passed_when_no_missing_norms(self, tmp_test_dir):
        """checks_passed is True when NORM_CATALOG is complete."""
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        report = generate_integrity_report(tmp_test_dir, drift, EXPECTED_OUTPUTS)
        assert report["checks_passed"] is True


class TestSkillExecution:
    """Tests for end-to-end skill execution."""

    def test_dry_run_does_not_create_files(self, tmp_test_dir, monkeypatch):
        """Dry-run mode should not write any files."""
        from vault_io import VAULT_ROOT

        monkeypatch.setattr("vault_sdd_init.VAULT_ROOT", tmp_test_dir)
        sdd = tmp_test_dir / "docs" / "sdd"

        # Invoke main with --dry-run
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "scripts" / "vault_sdd_init.py"),
                "--dry-run",
                "--vault-root",
                str(tmp_test_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert sdd.exists() is False or not any(sdd.iterdir()), "Dry-run created files"

    def test_skill_idempotency(self, tmp_test_dir):
        """Running skill twice produces same files."""
        from vault_io import VAULT_ROOT

        # Run twice with same input
        # Compare hashes of generated files
        # (idempotency means same content for same vault state)
        drift = {"version": "v36.0", "missing_norms": [], "warnings": []}
        run1 = {f: GENERATORS[f](tmp_test_dir, drift) for f in GENERATORS}
        run2 = {f: GENERATORS[f](tmp_test_dir, drift) for f in GENERATORS}
        for f in run1:
            assert run1[f] == run2[f], f"{f} not idempotent"
