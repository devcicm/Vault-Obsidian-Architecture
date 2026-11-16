"""A-06: process timeouts stop new writes; ledger fences remain independently valid."""
import json
import os
from pathlib import Path
import threading

import pytest
import vault_errors
from vault_io import atomic_write_text, set_vault_root
from vault.kernel.ledger import EscrituraCancelada, cancelar_escrituras, descartar_cancelacion
from apoyo import esperar_condicion, proceso_activo

PLAZO = 10.0
# The budget includes worker startup, which exceeded 3 s on a loaded host;
# the callback must be admitted before the timeout can be observed.
PRESUPUESTO = 8


def tool_lenta():
    raiz = Path(os.environ["TIMEOUT_PROBE_ROOT"])
    (raiz / "worker.pid").write_text(str(os.getpid()), encoding="utf-8")
    esperar_condicion(lambda: False, timeout=30)
    atomic_write_text(raiz / "late.txt", "late")


def tool_rapida():
    atomic_write_text(Path(os.environ["TIMEOUT_PROBE_ROOT"]) / "despues.txt", "escrito")
    return 0


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMEOUT_PROBE_ROOT", str(tmp_path))
    previous = set_vault_root(tmp_path)
    yield tmp_path
    set_vault_root(previous)


def _envelope(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _assert_worker_stopped(raiz):
    pid_path = raiz / "worker.pid"
    assert esperar_condicion(pid_path.exists, timeout=5), "Callback must start"
    pid = int(pid_path.read_text(encoding="utf-8"))
    assert esperar_condicion(lambda: not proceso_activo(pid), timeout=5), (
        "The timed-out process must be gone before checking for late writes"
    )


def test_tras_el_timeout_no_hay_escritura_nueva(raiz, capsys):
    assert vault_errors.wrap_main(tool_lenta, "test_timeout", timeout=PRESUPUESTO) == 1
    assert _envelope(capsys)["error_code"] == "TOOL_TIMEOUT"
    _assert_worker_stopped(raiz)
    assert not (raiz / "late.txt").exists()


def test_el_envelope_declara_el_limite_y_el_desconocimiento(raiz, capsys):
    assert vault_errors.wrap_main(tool_lenta, "test_timeout", timeout=PRESUPUESTO) == 1
    envelope = _envelope(capsys)
    assert envelope["error_code"] == "TOOL_TIMEOUT"
    assert envelope["args"]["timeout_seconds"] == PRESUPUESTO
    assert envelope["args"]["reintentar"] is False
    assert envelope["args"]["escrituras"] == "desconocidas"
    _assert_worker_stopped(raiz)
    assert not (raiz / "late.txt").exists()


def test_el_timeout_deja_su_testigo(raiz, capsys):
    assert vault_errors.wrap_main(tool_lenta, "test_timeout", timeout=PRESUPUESTO) == 1
    envelope = _envelope(capsys)
    assert envelope["error_code"] == "TOOL_TIMEOUT"
    assert envelope["timestamp"]
    assert "TOOL_TIMEOUT" in (raiz / "00_System" / ".tool-trace.json").read_text(encoding="utf-8")
    _assert_worker_stopped(raiz)
    assert not (raiz / "late.txt").exists()


def test_una_ejecucion_nueva_puede_volver_a_escribir(raiz, capsys):
    assert vault_errors.wrap_main(tool_lenta, "test_timeout", timeout=PRESUPUESTO) == 1
    capsys.readouterr()
    _assert_worker_stopped(raiz)
    assert not (raiz / "late.txt").exists()
    assert vault_errors.wrap_main(tool_rapida, "test_timeout", timeout=15) == 0
    assert (raiz / "despues.txt").read_text(encoding="utf-8").startswith("escrito")


def test_la_escritura_directa_tambien_se_niega(raiz):
    """La valla está en el dueño de la escritura, no en un wrapper."""
    cancelar_escrituras()
    try:
        with pytest.raises(EscrituraCancelada):
            atomic_write_text(raiz / "nope.txt", "no debe existir")
        assert not (raiz / "nope.txt").exists()
    finally:
        descartar_cancelacion()

    atomic_write_text(raiz / "si.txt", "ahora si")
    assert (raiz / "si.txt").is_file()


def test_la_valla_no_alcanza_a_otros_hilos(raiz):
    """La valla es del hilo fugado, no del proceso.

    Una valla de proceso cerraba el portón a todo lo que venía después en
    ese proceso —medido el 2026-11-09: el test de concurrencia del
    change-log fallaba porque el timeout de un test anterior había dejado
    la valla cerrada—. Aquí se fija ese límite.
    """
    cancelar_escrituras()
    errores = []

    def intento():
        try:
            atomic_write_text(raiz / "de-otro-hilo.txt", "permitido")
        except EscrituraCancelada as exc:
            errores.append(exc)

    try:
        hilo = threading.Thread(target=intento)
        hilo.start()
        hilo.join(timeout=PLAZO)
        assert not hilo.is_alive()
        assert not errores, "otro hilo quedó frenado por la valla ajena"
        assert (raiz / "de-otro-hilo.txt").is_file()
    finally:
        descartar_cancelacion()
