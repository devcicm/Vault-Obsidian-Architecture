"""The process-specific timeout is stronger than the generic error catalog."""
import json
import os
from pathlib import Path

import vault_errors
from apoyo import esperar_condicion, proceso_activo


def lenta():
    pid_path = Path(os.environ["TIMEOUT_PID_PATH"])
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    esperar_condicion(lambda: False, timeout=30)


def test_timeout_declara_proceso_detenido_y_escrituras_previas(capsys, tmp_path, monkeypatch):
    pid_path = tmp_path / "worker.pid"
    monkeypatch.setenv("TIMEOUT_PID_PATH", str(pid_path))
    # The budget includes worker startup (about a second on a loaded Windows
    # host), so a one-second budget made "Callback must start" a timing race.
    assert vault_errors.wrap_main(lenta, "probe_lenta", timeout=8) == 1
    envelope = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert envelope["error_code"] == "TOOL_TIMEOUT"
    assert "process tree has stopped" in envelope["message"]
    assert envelope["args"]["reintentar"] is False
    assert esperar_condicion(pid_path.exists, timeout=5), "Callback must start"
    pid = int(pid_path.read_text(encoding="utf-8"))
    assert esperar_condicion(lambda: not proceso_activo(pid), timeout=5)


def test_el_catalogo_no_promete_que_se_termina():
    from vault.kernel.errores import ERROR_CATALOG

    assert "terminada" not in ERROR_CATALOG["TOOL_TIMEOUT"]["message"]
