#!/usr/bin/env python3
"""Shared pytest fixtures for vault tests.

Run from repo root:
    python -m pytest tests/ -v
"""

import sys
import os
import time
from pathlib import Path

import pytest

from sandbox_fixture import bootstrap as bootstrap_sandbox
from sandbox_fixture import clean as clean_sandbox
from sandbox_fixture import ready as sandbox_ready

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Ensure scripts/ is importable for all test modules
sys.path.insert(0, str(SCRIPTS_DIR))


def _es_worker(session) -> bool:
    """True en un proceso worker de pytest-xdist; el controller no lo tiene."""
    return hasattr(session.config, "workerinput")


def pytest_sessionstart(session):
    """Materializa el runtime ignorado desde fuentes versionadas antes de colectar.

    Una ejecución normal de pytest no presupone restos de `vault-sandbox/`.
    Si un orquestador ya hizo el bootstrap para ejecutar gates después de la
    suite, el hook no toma propiedad del runtime y no lo elimina.

    Con xdist solo el controller decide el bootstrap. Antes, cada worker lo
    comprobaba por su cuenta: hasta ocho bootstrap concurrentes podían pisar
    el mismo `vault-sandbox/`, y la limpieza de un worker borraba el runtime
    que otro seguía usando (medido 2026-10-18 con `-n auto`). El worker espera,
    acotado, a que el controller lo deje listo; el `pytest_sessionfinish` del
    controller corre después de los de todos los workers, así que la limpieza
    tampoco puede pisar a nadie.
    """
    # Red anti-contención para toda la suite: con `-n auto` la máquina va
    # cargada y el límite de 60s por tool (default de VAULT_TOOL_TIMEOUT)
    # mataba setups enteros de vault_init y pasos de doc_counts sin que
    # hubiera ningún defecto de producto (medido 2026-10-18: 4 ERROR de
    # setup en una corrida y ninguno en la siguiente, misma cabeza). El
    # valor lo puede subir quien lance la suite; nadie lo baja.
    os.environ.setdefault("VAULT_TOOL_TIMEOUT", "180")
    if _es_worker(session):
        plazo = time.monotonic() + 900
        while not sandbox_ready():
            if time.monotonic() > plazo:
                raise RuntimeError(
                    "vault-sandbox no quedó listo: el bootstrap del controller "
                    "de la corrida no terminó en 900s"
                )
            time.sleep(1)
        session.config._sandbox_fixture_owned = False
        return
    if not sandbox_ready():
        bootstrap_sandbox()
        session.config._sandbox_fixture_owned = True
    else:
        session.config._sandbox_fixture_owned = False


def pytest_collection_modifyitems(config, items):
    """`VAULT_SHARD=i/n`: corre solo el trozo `i` de `n` (ver `reparto.py`).

    Sin la variable no cambia nada. Con xdist, cada worker colecta y reparte
    igual porque el reparto es determinista.
    """
    import reparto

    shard = reparto.leer_shard(os.environ.get("VAULT_SHARD"))
    if shard is None:
        return
    indice, total = shard
    asignacion = reparto.repartir((reparto.modulo_de(i.nodeid) for i in items), total)
    quedan, fuera = [], []
    for item in items:
        (quedan if asignacion[reparto.modulo_de(item.nodeid)] == indice - 1
         else fuera).append(item)
    if fuera:
        config.hook.pytest_deselected(items=fuera)
        items[:] = quedan


def pytest_sessionfinish(session, exitstatus):
    if not _es_worker(session) and getattr(session.config, "_sandbox_fixture_owned", False):
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
