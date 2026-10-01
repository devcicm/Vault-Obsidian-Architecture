"""F4 — `NOTE_LOCKED` solo cuando el lock de la nota no se consiguió.

`NOTE_LOCKED` promete «no se escribió nada». Con `except TimeoutError`
alrededor de todo el `with file_lock(...)`, el timeout de un lock interno —el
del índice de sección que toma la escritura— salía con ese mismo código y la
nota ya escrita: un envelope que afirma lo contrario de lo que pasó.
"""

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from vault_fs import tomar_lock  # noqa: E402


def _ocupar(objetivo: Path) -> Path:
    """Simula a otro proceso con el lock de `objetivo` recién tomado."""
    lock_dir = objetivo.parent / ".locks" / f"{objetivo.name}.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner.json").write_text(
        json.dumps({"pid": 0, "createdAt": time.time(), "token": "otro"}), encoding="utf-8")
    return lock_dir


def test_tomar_lock_ocupado_devuelve_none(tmp_path):
    objetivo = tmp_path / "nota.md"
    ocupado = _ocupar(objetivo)
    assert tomar_lock(objetivo, 0.2) is None
    assert (ocupado / "owner.json").exists()


def test_un_timeout_interno_no_se_confunde_con_el_lock(tmp_path):
    objetivo = tmp_path / "nota.md"
    lock = tomar_lock(objetivo, 1.0)
    assert lock is not None
    with pytest.raises(TimeoutError):
        with lock:
            raise TimeoutError("lock del índice de sección")
    # Y lo soltó al salir: se puede volver a tomar.
    otra = tomar_lock(objetivo, 1.0)
    assert otra is not None
    with otra:
        pass


def test_vault_append_no_dice_note_locked_si_el_timeout_es_de_dentro(tmp_path, monkeypatch):
    import vault_append
    import vault_io

    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "07_Knowledge" / "log.md").write_text("# log\n", encoding="utf-8")
    monkeypatch.setattr(vault_append, "get_vault_root", lambda: raiz)

    def escritura_que_espera_a_otro_lock(*a, **k):
        raise TimeoutError("Timeout waiting for lock: 99_Index/.locks/x")

    monkeypatch.setattr(vault_append, "atomic_write_text", escritura_que_espera_a_otro_lock)
    monkeypatch.setattr(vault_io, "atomic_write_text", escritura_que_espera_a_otro_lock)
    with pytest.raises(TimeoutError):
        r = vault_append.vault_append("07_Knowledge/log.md", "x")
        pytest.fail(f"devolvió un envelope en vez de propagar: {r}")
