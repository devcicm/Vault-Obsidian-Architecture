#!/usr/bin/env python3
"""Shared pytest fixtures for vault tests.

Run from repo root:
    python -m pytest tests/ -v
"""

import sys
from pathlib import Path

import pytest

from sandbox_fixture import bootstrap as bootstrap_sandbox
from sandbox_fixture import clean as clean_sandbox
from sandbox_fixture import ready as sandbox_ready

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Ensure scripts/ is importable for all test modules
sys.path.insert(0, str(SCRIPTS_DIR))


def pytest_sessionstart(session):
    """Materializa el runtime ignorado desde fuentes versionadas antes de colectar.

    Una ejecución normal de pytest no presupone restos de `vault-sandbox/`.
    Si un orquestador ya hizo el bootstrap para ejecutar gates después de la
    suite, el hook no toma propiedad del runtime y no lo elimina.
    """
    if not sandbox_ready():
        bootstrap_sandbox()
        session.config._sandbox_fixture_owned = True
    else:
        session.config._sandbox_fixture_owned = False


def pytest_sessionfinish(session, exitstatus):
    if getattr(session.config, "_sandbox_fixture_owned", False):
        clean_sandbox()


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


@pytest.fixture(autouse=True)
def _raiz_de_vault_limpia():
    """Ningún test hereda el vault que dejó apuntando el anterior.

    `set_vault_root()` reancla constantes de módulo en todo el proceso, así que
    un test que lo llama —o una tool con `--root` que lo llama por él— deja el
    intérprete apuntando a un directorio temporal que ya no existe. Se veía como
    fallos que dependen del orden de los ficheros, y el diagnóstico costaba
    porque el síntoma aparecía en un test que no había tocado nada.

    Esto no sustituye al arreglo de fondo —que los módulos resuelvan la raíz al
    usarla y no al importarla, AP-49— sino que impide que la fuga se propague
    mientras quedan contextos sin migrar.
    """
    yield
    import vault_io

    vault_io.reset_vault_root()
