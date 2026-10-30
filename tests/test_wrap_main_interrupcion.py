"""A-09 — Ctrl-C durante la espera de wrap_main debe salir con envelope, no con traceback."""
import json
import threading

import vault_errors


def test_ctrl_c_en_la_espera_emite_interrupted(monkeypatch, capsys):
    liberar = threading.Event()
    real_join = threading.Thread.join

    def join_interrumpido(self, timeout=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(threading.Thread, "join", join_interrumpido)
    try:
        rc = vault_errors.wrap_main(lambda: liberar.wait(5) and 0, "tool_de_prueba", timeout=5)
    finally:
        liberar.set()
        monkeypatch.setattr(threading.Thread, "join", real_join)
    assert rc == 130
    salida = capsys.readouterr().out
    assert json.loads(salida[salida.index("{"):])["error_code"] == "INTERRUPTED"
