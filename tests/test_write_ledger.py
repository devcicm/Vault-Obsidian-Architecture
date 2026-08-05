"""Tests del ledger de escrituras (`vault_io.write_report`) — el motor de AP-37.

La norma pasó de baseline a guard duro porque el indicador de trabajo dejó de
ser algo que cada tool **afirma** y pasó a ser algo que se **mide** donde la
escritura ocurre. Si el ledger miente, AP-37 vuelve a ser decorativo, así que
lo que se comprueba aquí es justamente que no mienta:

  - una escritura nueva cuenta como `created`,
  - reescribir con contenido distinto cuenta como `updated`,
  - reescribir con el MISMO contenido cuenta como `unchanged` y NO suma a
    `written` — es el caso que la norma nació para hacer visible,
  - el contador es por hilo, porque la CLI consolidada ejecuta operaciones a la vez.
"""
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_io  # noqa: E402


@pytest.fixture(autouse=True)
def ledger_limpio():
    vault_io.write_ledger_reset()
    yield
    vault_io.write_ledger_reset()


def test_una_escritura_nueva_cuenta_como_created(tmp_path):
    vault_io.atomic_write_text(tmp_path / "n.md", "hola")
    assert vault_io.write_report() == {
        "created": 1, "updated": 0, "unchanged": 0, "written": 1
    }


def test_reescribir_con_otro_contenido_cuenta_como_updated(tmp_path):
    destino = tmp_path / "n.md"
    vault_io.atomic_write_text(destino, "hola")
    vault_io.write_ledger_reset()
    vault_io.atomic_write_text(destino, "adios")
    assert vault_io.write_report()["updated"] == 1
    assert vault_io.write_report()["written"] == 1


def test_reescribir_lo_mismo_no_cuenta_como_trabajo(tmp_path):
    """El caso que originó AP-37: una ejecución que no cambió nada.

    Antes era indistinguible de un éxito real porque ambas devolvían `ok: true`.
    """
    destino = tmp_path / "n.md"
    vault_io.atomic_write_text(destino, "hola")
    vault_io.write_ledger_reset()
    vault_io.atomic_write_text(destino, "hola")
    reporte = vault_io.write_report()
    assert reporte["unchanged"] == 1
    assert reporte["written"] == 0, "una escritura idéntica no es trabajo"


def test_el_reset_pone_todo_a_cero(tmp_path):
    vault_io.atomic_write_text(tmp_path / "n.md", "hola")
    vault_io.write_ledger_reset()
    assert vault_io.write_report() == {
        "created": 0, "updated": 0, "unchanged": 0, "written": 0
    }


def test_el_contador_no_se_mezcla_entre_hilos(tmp_path):
    """La CLI consolidada corre varias operaciones a la vez.

    Con un contador de módulo, el trabajo de una operación aparecería en el
    reporte de otra — y el indicador dejaría de ser verificable.
    """
    resultados = {}

    def escribe(nombre, cuantos):
        vault_io.write_ledger_reset()
        for i in range(cuantos):
            vault_io.atomic_write_text(tmp_path / f"{nombre}-{i}.md", "x")
        resultados[nombre] = vault_io.write_report()["created"]

    hilos = [
        threading.Thread(target=escribe, args=("a", 3)),
        threading.Thread(target=escribe, args=("b", 5)),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados == {"a": 3, "b": 5}


def test_record_raw_write_mide_sin_escribir(tmp_path):
    """Para el índice de sección, que escribe en crudo a propósito (recursión)."""
    destino = tmp_path / "index.md"
    assert vault_io.record_raw_write(destino, "contenido") == "created"
    assert not destino.exists(), "record_raw_write clasifica, no escribe"
    assert vault_io.write_report()["created"] == 1
