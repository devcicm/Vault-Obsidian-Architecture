"""Interruption during process supervision stops its tree and emits an envelope."""
import json
import vault_errors
from vault.kernel import aislamiento
from apoyo import esperar_condicion


def lenta():
    esperar_condicion(lambda: False, timeout=30)


def _sigint_al_proceso_tras(segundos):
    """Deliver a real SIGINT to this process: the Linux wait turns it into cancellation."""
    import os
    import signal
    import threading

    timer = threading.Timer(segundos, os.kill, (os.getpid(), signal.SIGINT))
    timer.start()
    return timer


def test_ctrl_c_en_la_espera_emite_interrupted(monkeypatch, capsys):
    import sys
    if sys.platform == "linux":
        timer = _sigint_al_proceso_tras(2)
        try:
            rc = vault_errors.wrap_main(lenta, "tool_de_prueba", timeout=20)
        finally:
            timer.cancel()
        assert rc == 130
        assert json.loads(capsys.readouterr().out)["error_code"] == "INTERRUPTED"
        return
    original_wait = aislamiento.subprocess.Popen.wait
    injected = False

    def interrupted(self, timeout=None):
        nonlocal injected
        if timeout is not None and not injected:
            injected = True
            raise KeyboardInterrupt
        return original_wait(self)

    monkeypatch.setattr(aislamiento.subprocess.Popen, "wait", interrupted)
    rc = vault_errors.wrap_main(lenta, "tool_de_prueba", timeout=5)
    assert rc == 130
    assert json.loads(capsys.readouterr().out)["error_code"] == "INTERRUPTED"
