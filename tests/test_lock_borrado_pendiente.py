"""F1/CIA-I — adquirir sobrevive a que otro proceso esté retirando `.locks/`.

Medido el 2026-10-05 en la ronda 13 (db37a5c): 1 de 12 procesos de
`test_file_lock_no_deja_entrar_a_dos_procesos` murió con
`[WinError 183] No se puede crear un archivo que ya existe: '…\\.locks'`.
Soltar el último lock retira `.locks/` vacío, y en Windows un directorio en
borrado pendiente sigue ocupando el nombre: `mkdir` lo da por existente,
`Path.mkdir(exist_ok=True)` comprueba `is_dir()`, ya no está, y relanza. Crear
el lock *dentro* de esa carpeta da `PermissionError` (WinError 5). Ninguna de
las dos es un error del llamante: es el mismo hueco que `FileNotFoundError`, y
se compite de nuevo.

Aquí se fuerza de forma determinista: el primer `mkdir` de la ruta elegida
falla como lo hace Windows en ese hueco, sin crear nada.
"""

import os
import pathlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_fs  # noqa: E402
from vault.autoria.conocimiento import _FileLock  # noqa: E402


def _fs_lock(nota):
    return vault_fs.file_lock(nota, timeout=2.0)


def _conocimiento_lock(nota):
    return _FileLock(nota, timeout=2.0)


def _hueco(monkeypatch, ruta: Path, error: type) -> list:
    """El primer `mkdir` de `ruta` falla con `error` sin crear nada."""
    real = os.mkdir
    disparos = []

    def mkdir(path, *args, **kwargs):
        if Path(path) == ruta and not disparos:
            disparos.append(error.__name__)
            raise error(f"simulado: {ruta} en borrado pendiente")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", mkdir)
    # Hasta 3.10, `Path.mkdir` no llama a `os.mkdir` sino a la copia que
    # `pathlib._NormalAccessor` guardó al importarse, y el hueco de `.locks`
    # no se disparaba: medido el 2026-10-15 en python:3.9-slim.
    if hasattr(pathlib, "_NormalAccessor"):
        monkeypatch.setattr(pathlib._NormalAccessor, "mkdir", staticmethod(mkdir))
    return disparos


@pytest.mark.parametrize("tomar", [_fs_lock, _conocimiento_lock], ids=["vault_fs", "conocimiento"])
@pytest.mark.parametrize(
    "que, error",
    [(".locks", FileExistsError), ("nota.md.lock", PermissionError)],
    ids=["raiz-pendiente", "lock-dentro-de-raiz-pendiente"],
)
def test_adquiere_tras_el_hueco_de_borrado_pendiente(tmp_path, monkeypatch, tomar, que, error):
    nota = tmp_path / "nota.md"
    raiz = tmp_path / ".locks"
    disparos = _hueco(monkeypatch, raiz if que == ".locks" else raiz / que, error)
    with tomar(nota):
        assert (raiz / "nota.md.lock").is_dir()
    assert disparos == [error.__name__]
    assert not raiz.exists()


@pytest.mark.parametrize("tomar", [_fs_lock, _conocimiento_lock], ids=["vault_fs", "conocimiento"])
def test_un_permiso_denegado_de_verdad_no_se_traga(tmp_path, monkeypatch, tomar):
    """Reintentar es para el hueco, no para una carpeta en la que no se puede escribir."""
    nota = tmp_path / "nota.md"
    real = os.mkdir

    def mkdir(path, *args, **kwargs):
        if Path(path).name == "nota.md.lock":
            raise PermissionError("simulado: sin permiso de escritura")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", mkdir)
    with pytest.raises(PermissionError):
        with (vault_fs.file_lock(nota, timeout=0.3) if tomar is _fs_lock else _FileLock(nota, timeout=0.3)):
            pass
