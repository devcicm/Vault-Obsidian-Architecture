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
