"""Soltar un lock no deja `.locks/` vacío en la carpeta de la nota.

Medido el 2026-10-05 al reindexar un vault real: quedaba un `.locks/` vacío en
cada una de sus 68 secciones, residuo en el vault del usuario sin nada dentro
que proteger. Retirarlo abre una carrera —otro proceso puede crear su lock
justo cuando la carpeta desaparece— y el segundo test la fuerza.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_fs  # noqa: E402


def test_soltar_el_ultimo_lock_retira_la_carpeta(tmp_path):
    nota = tmp_path / "sec" / "nota.md"
    nota.parent.mkdir()
    with vault_fs.file_lock(nota, timeout=2):
        assert (nota.parent / ".locks" / "nota.md.lock").is_dir()
    assert not (nota.parent / ".locks").exists()


def test_la_carpeta_se_conserva_si_otro_lock_sigue_dentro(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    with vault_fs.file_lock(a, timeout=2):
        with vault_fs.file_lock(b, timeout=2):
            pass
        assert (tmp_path / ".locks" / "a.md.lock").is_dir()
    assert not (tmp_path / ".locks").exists()


def test_adquirir_sobrevive_a_que_retiren_la_carpeta(tmp_path, monkeypatch):
    """Otro proceso retira `.locks/` entre el `mkdir` del padre y el del lock."""
    nota = tmp_path / "nota.md"
    original = vault_fs.os.mkdir
    retirada = []

    def mkdir_con_carrera(path, *args, **kwargs):
        if not retirada and Path(path).name == "nota.md.lock":
            retirada.append(True)
            Path(path).parent.rmdir()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(vault_fs.os, "mkdir", mkdir_con_carrera)
    with vault_fs.file_lock(nota, timeout=2) as lock_dir:
        assert lock_dir.is_dir()
    assert retirada
