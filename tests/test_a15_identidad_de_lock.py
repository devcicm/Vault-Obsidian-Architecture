"""A-15 — dos grafías de una misma nota comparten lock en un disco sin caja.

`bloqueo.py` documentaba que `Nota.md` y `nota.md` eran dos locks hasta que la
nota existiera. Ahora el nombre del lock se pliega cuando el disco no distingue
mayúsculas y se deja intacto cuando sí, que es lo que protege a dos notas
distintas de fundirse.
"""
import os

from vault.kernel import bloqueo


def test_en_un_disco_sin_caja_las_dos_grafias_comparten_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(bloqueo, "distingue_mayusculas", lambda carpeta: False)
    a = bloqueo.rutas_de_lock(tmp_path / "Nota.md")[1].name
    b = bloqueo.rutas_de_lock(tmp_path / "nota.md")[1].name
    assert a == b


def test_en_un_disco_con_caja_siguen_siendo_dos_locks(tmp_path, monkeypatch):
    monkeypatch.setattr(bloqueo, "distingue_mayusculas", lambda carpeta: True)
    a = bloqueo.rutas_de_lock(tmp_path / "Nota.md")[1].name
    b = bloqueo.rutas_de_lock(tmp_path / "nota.md")[1].name
    assert a != b


def test_la_sonda_coincide_con_lo_que_hace_el_disco_de_verdad(tmp_path):
    carpeta = tmp_path / "Carpeta"
    carpeta.mkdir()
    bloqueo.distingue_mayusculas.cache_clear()
    esperado = not os.path.exists(tmp_path / "cARPETA")
    assert bloqueo.distingue_mayusculas(carpeta) is esperado


def test_dos_procesos_con_grafias_distintas_se_excluyen_de_verdad(tmp_path):
    """A-15 with real processes: a not-yet-existing note under two spellings."""
    import subprocess
    import pytest
    from apoyo import esperar_condicion, lanzar_python
    from vault.kernel.fs import file_lock

    bloqueo.distingue_mayusculas.cache_clear()
    if bloqueo.distingue_mayusculas(tmp_path):
        pytest.skip("case-sensitive filesystem: two spellings are two notes")
    tomado = tmp_path / "tomado"
    soltar = tmp_path / "soltar"
    holder = lanzar_python(
        "-c",
        "import sys, pathlib; from vault.kernel.fs import file_lock; from apoyo import esperar_condicion\n"
        "r = pathlib.Path(sys.argv[1])\n"
        "with file_lock(r / 'Nota.md', timeout=30):\n"
        "    (r / 'tomado').touch()\n"
        "    esperar_condicion((r / 'soltar').exists, timeout=60)\n",
        str(tmp_path), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        assert esperar_condicion(tomado.exists, timeout=60), "holder must take the lock"
        assert not (tmp_path / "Nota.md").exists() and not (tmp_path / "nota.md").exists()
        with pytest.raises(TimeoutError):
            with file_lock(tmp_path / "nota.md", timeout=1.5, stale_after=120):
                pass
    finally:
        soltar.touch()
        holder.wait(timeout=60)
    with file_lock(tmp_path / "nota.md", timeout=10):
        pass  # released by the other process: the alias is free again
