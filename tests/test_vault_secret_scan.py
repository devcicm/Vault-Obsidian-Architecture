#!/usr/bin/env python3
"""Tests for vault_secret_scan (I1/I5 fix verification).

Run from repo root:
    python -m pytest tests/test_vault_secret_scan.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from vault_secret_scan import scan_content, has_blocking_findings, vault_write_hook


class TestSecretScan:
    """Tests for secret pattern detection."""

    def test_aws_access_key_detected(self):
        """AWS access key is detected as critical."""
        text = "Mi AWS key es AKIAIOSFODNN7EXAMPLE"
        findings = scan_content(text)
        assert any(f["pattern_id"] == "aws_access_key" for f in findings)
        assert has_blocking_findings(findings)

    def test_github_token_detected(self):
        """GitHub personal token is detected as critical."""
        text = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        findings = scan_content(text)
        assert any(f["pattern_id"] == "github_personal_token" for f in findings)
        assert has_blocking_findings(findings)

    def test_bearer_token_detected(self):
        """Bearer token is detected as critical."""
        text = "Authorization: Bearer abc123def456ghi789jkl012mno345pqr678"
        findings = scan_content(text)
        assert any(f["pattern_id"] == "bearer_token" for f in findings)
        assert has_blocking_findings(findings)

    def test_private_key_marker_detected(self):
        """Private key marker is detected as critical."""
        text = "-----BEGIN RSA PRIVATE KEY-----"
        findings = scan_content(text)
        assert any(f["pattern_id"] == "private_key_marker" for f in findings)
        assert has_blocking_findings(findings)

    def test_jwt_detected(self):
        """JWT token is detected as high severity."""
        text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        findings = scan_content(text)
        assert any(f["pattern_id"] == "jwt_token" for f in findings)

    def test_clean_content_no_findings(self):
        """Content without secrets has no findings."""
        text = "Esta es una nota sobre el vault. Sin secretos aquí."
        findings = scan_content(text)
        assert findings == []
        assert not has_blocking_findings(findings)

    def test_redaction_in_findings(self):
        """Findings include redacted matches (not raw secrets)."""
        text = "AKIAIOSFODNN7EXAMPLE"
        findings = scan_content(text)
        assert len(findings) >= 1
        for f in findings:
            assert "AKIAIOSFODNN7EXAMPLE" not in f["match_redacted"], (
                "Raw secret leaked in redacted match"
            )
            assert "*" in f["match_redacted"]

    def test_vault_write_hook_blocks_critical(self):
        """Hook returns ok=False for critical findings."""
        text = "AKIAIOSFODNN7EXAMPLE"
        ok, findings = vault_write_hook(text)
        assert ok is False
        assert len(findings) >= 1

    def test_vault_write_hook_allows_clean(self):
        """Hook returns ok=True for clean content."""
        text = "Nota limpia sin secretos."
        ok, findings = vault_write_hook(text)
        assert ok is True
        assert findings == []
