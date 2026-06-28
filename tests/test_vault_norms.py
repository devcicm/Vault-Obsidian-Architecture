#!/usr/bin/env python3
"""Tests for vault_norms catalog completeness.

Run from repo root:
    python -m pytest tests/test_vault_norms.py -v

Verifies the NORM_CATALOG has all expected norms including AP-24 and AP-25
which were registered in v36.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from vault_norms import NORM_CATALOG


class TestNormCatalog:
    """Tests for NORM_CATALOG completeness — A2/A3 fix verification."""

    def test_has_all_ap_antipatterns(self):
        """Catalog includes AP-01 through AP-25."""
        codes = {n["code"] for n in NORM_CATALOG}
        for i in range(1, 26):
            code = f"AP-{i:02d}"
            assert code in codes, f"Missing norm: {code}"

    def test_ap24_bracket_imbalance_registered(self):
        """AP-24 must be in catalog with correct fields."""
        ap24 = next((n for n in NORM_CATALOG if n["code"] == "AP-24"), None)
        assert ap24 is not None, "AP-24 not found in NORM_CATALOG"
        assert (
            ap24["name"]
            == "Bracket imbalance — corchetes sin pareja, anidados o invertidos"
        )
        assert ap24["type"] == "antipattern"
        assert ap24["severity"] == "high"
        assert "guard+audit" == ap24["enforcement"]
        assert "vault_write" in ap24["tools_enforcing"]
        assert "vault_audit" in ap24["tools_detecting"]

    def test_ap25_mermaid_registered(self):
        """AP-25 must be in catalog with correct fields."""
        ap25 = next((n for n in NORM_CATALOG if n["code"] == "AP-25"), None)
        assert ap25 is not None, "AP-25 not found in NORM_CATALOG"
        assert (
            ap25["name"] == "Mermaid diagram syntax errors — nodos/tipos no definidos"
        )
        assert ap25["type"] == "antipattern"
        assert ap25["severity"] == "medium"
        assert ap25["enforcement"] == "audit"
        assert "vault_mermaid_check" in ap25["tools_detecting"]

    def test_has_naming_conventions(self):
        """Catalog includes CN-01, CN-02, CN-03."""
        codes = {n["code"] for n in NORM_CATALOG}
        for cn in ("CN-01", "CN-02", "CN-03"):
            assert cn in codes, f"Missing naming convention: {cn}"

    def test_has_session_protocol(self):
        """Catalog includes SP-01, SP-02, SP-03."""
        codes = {n["code"] for n in NORM_CATALOG}
        for sp in ("SP-01", "SP-02", "SP-03"):
            assert sp in codes, f"Missing session protocol: {sp}"

    def test_all_norms_have_required_fields(self):
        """Every norm entry has the required schema."""
        required = {"code", "name", "type", "category", "severity", "enforcement"}
        for norm in NORM_CATALOG:
            missing = required - set(norm.keys())
            assert not missing, f"{norm.get('code', '?')} missing fields: {missing}"
