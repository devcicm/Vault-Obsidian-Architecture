"""Test: scripts/*.py stems no colliden con packages/stdlib/deps."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _colisiones(stems: set[str], packages: set[str], stdlib: set[str], deps: set[str]) -> set[str]:
    return stems & (packages | stdlib | deps)


def test_scripts_stems_no_colisionan_con_packages():
    cfg_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    packages_match = re.search(r"^packages\s*=\s*\[(.*?)\]", cfg_text, re.DOTALL | re.MULTILINE)
    packages = set(re.findall(r'"([^"]+)"', packages_match.group(1))) if packages_match else set()

    scripts_stems = {
        p.stem
        for p in (REPO_ROOT / "scripts").glob("*.py")
        if p.name != "__init__.py"
    }

    collision = _colisiones(scripts_stems, packages, set(), set())
    assert not collision, f"scripts stems colliden con packages: {collision}"


def test_scripts_stems_no_colisionan_con_stdlib():
    if sys.version_info < (3, 10):
        pytest.skip("sys.stdlib_module_names requires Python 3.10+")

    stdlib_names = getattr(sys, "stdlib_module_names", set())
    scripts_stems = {
        p.stem
        for p in (REPO_ROOT / "scripts").glob("*.py")
        if p.name != "__init__.py"
    }

    collision = _colisiones(scripts_stems, set(), stdlib_names, set())
    assert not collision, f"scripts stems colliden con stdlib: {collision}"


def test_scripts_stems_no_colisionan_con_dependencias():
    cfg_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    deps_match = re.search(r'^dependencies\s*=\s*\[(.*?)\]', cfg_text, re.DOTALL | re.MULTILINE)
    deps = set(re.findall(r'"([^"]+)"', deps_match.group(1))) if deps_match else set()
    dep_import_names = set()
    for dep in deps:
        base = re.split(r'[><=!]', dep)[0].strip().lower().replace("-", "_")
        dep_import_names.add(base)
        if base == "pyyaml":
            dep_import_names.add("yaml")
    scripts_stems = {
        p.stem
        for p in (REPO_ROOT / "scripts").glob("*.py")
        if p.name != "__init__.py"
    }

    targets = dep_import_names
    collision = _colisiones(scripts_stems, set(), set(), targets)
    assert not collision, f"scripts stems colliden con deps: {collision}"


def test_vault_regex_en_packages_seria_colision():
    cfg_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    packages_match = re.search(r"^packages\s*=\s*\[(.*?)\]", cfg_text, re.DOTALL | re.MULTILINE)
    packages = set(re.findall(r'"([^"]+)"', packages_match.group(1))) if packages_match else set()

    scripts_stems = {
        p.stem
        for p in (REPO_ROOT / "scripts").glob("*.py")
        if p.name != "__init__.py"
    }

    with_vault_regex = packages | {"vault_regex"}
    collision = _colisiones(scripts_stems, with_vault_regex, set(), set())
    assert "vault_regex" in collision, (
        "vault_regex en packages causa colision con scripts/vault_regex.py"
    )
