"""Independent Linux lifetime invariants, retained as regression probes."""

import json
import subprocess
import sys
from pathlib import Path
import pytest
import vault_errors
from vault.kernel import aislamiento
from test_wrap_main_process import probe  # noqa: F401 ? shared pytest fixture
from test_wrap_main_process import session_escape_writer, nested_session_escape_writer
from apoyo import esperar_condicion, lanzar_python

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Linux subreaper contract"
)


def assert_gone(root):
    markers = list(root.glob("*.pid"))
    assert markers
    for marker in markers:
        assert not Path("/proc", marker.read_text()).exists(), marker.name


def test_unrelated_sibling_survives_timeout(probe, capsys):
    sibling = lanzar_python(
        "-c", "import threading; threading.Event().wait(30)",
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert vault_errors.wrap_main(session_escape_writer, "review", timeout=10) == 1
        assert json.loads(capsys.readouterr().out)["error_code"] == "TOOL_TIMEOUT"
        assert_gone(probe)
        assert sibling.poll() is None
    finally:
        sibling.terminate()
        sibling.wait(timeout=5)
        (probe / "release").touch()


def test_nested_interruption_reaps_all_owned_pids(probe, capsys, monkeypatch):
    import os
    import signal
    import threading

    def interrupt_when_escaped():
        # A real SIGINT: the Linux wait turns it into a cancellation request.
        if esperar_condicion((probe / "escaped.pid").exists, timeout=15):
            os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=interrupt_when_escaped, daemon=True).start()
    try:
        assert (
            vault_errors.wrap_main(nested_session_escape_writer, "review", timeout=20)
            == 130
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == "INTERRUPTED"
        assert_gone(probe)
        assert not (probe / "escaped-write.txt").exists()
    finally:
        (probe / "release").touch()


def test_failed_cleanup_ack_never_claims_stopped(probe, capsys, monkeypatch):
    original = aislamiento.subprocess.Popen

    def unverified(command, *a, **k):
        if "aislamiento_linux import supervisar" in command[2]:
            command = list(command)
            command[2] = command[2].replace(
                " code = entry(sys.argv[1])",
                " import vault.kernel.aislamiento_linux as probe\n original=probe._stop_tree\n def unverified():\n  original()\n  raise probe.LinuxContainmentError('PRIVATE-CLEANUP-CANARY')\n probe._stop_tree=unverified\n code = entry(sys.argv[1])",
            )
            assert "PRIVATE-CLEANUP-CANARY" in command[2], "Injection must reach the supervisor"
        return original(command, *a, **k)

    monkeypatch.setattr(aislamiento.subprocess, "Popen", unverified)
    try:
        assert vault_errors.wrap_main(session_escape_writer, "review", timeout=10) == 1
        output = capsys.readouterr().out
        payload = json.loads(output)
        assert payload["error_code"] == "UNEXPECTED_ERROR"
        assert "has stopped" not in output and "PRIVATE-CLEANUP-CANARY" not in output
        assert_gone(probe)
    finally:
        (probe / "release").touch()
