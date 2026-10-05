"""`vault_knowledge_save` y el resto de escritores se excluyen sobre la misma nota.

Medido el 2026-10-05: el lock propio de `vault.autoria.conocimiento` se
llamaba `<stem>.lock` y el de `vault_fs.file_lock` —el de `vault_write`,
`vault_append`…— `<nombre>.md.lock`. Dos directorios distintos para la misma
nota: cada uno tomaba el suyo y escribían a la vez. Además dejaba `.locks/`
vacío al soltar.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_fs  # noqa: E402
from vault.autoria.conocimiento import _FileLock  # noqa: E402


def test_espera_al_lock_de_vault_fs(tmp_path):
    nota = tmp_path / "jwt.md"
    with vault_fs.file_lock(nota, timeout=2):
        with pytest.raises(TimeoutError):
            _FileLock(nota, timeout=0.3).acquire()


def test_vault_fs_espera_al_suyo(tmp_path):
    nota = tmp_path / "jwt.md"
    with _FileLock(nota, timeout=2):
        with pytest.raises(TimeoutError):
            with vault_fs.file_lock(nota, timeout=0.3):
                pass


def test_no_deja_locks_vacio(tmp_path):
    nota = tmp_path / "jwt.md"
    with _FileLock(nota, timeout=2):
        pass
    assert not (tmp_path / ".locks").exists()
