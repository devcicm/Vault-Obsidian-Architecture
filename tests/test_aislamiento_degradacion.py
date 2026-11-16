"""The supervisor acknowledges cleanup failure without a false stopped claim."""
import json
import os
import time
from types import SimpleNamespace

from vault.kernel import aislamiento_linux


def test_supervisor_exposes_failed_cleanup_acknowledgment(tmp_path, monkeypatch):
    request = tmp_path / "request.json"
    # supervisar runs in-process here, so its "caller" is this process's parent.
    request.write_text(json.dumps({"deadline": time.monotonic() + 20,
                                   "caller_pid": os.getppid(),
                                   "worker_command": ["unused-test-command"]}), encoding="utf-8")
    worker = SimpleNamespace(returncode=1, poll=lambda: 1)
    monkeypatch.setattr(aislamiento_linux, "_prepare", lambda: None)
    monkeypatch.setattr(aislamiento_linux.subprocess, "Popen", lambda *a, **k: worker)

    def failed_cleanup():
        raise RuntimeError("PRIVATE-CLEANUP-CANARY")

    monkeypatch.setattr(aislamiento_linux, "_stop_tree", failed_cleanup)
    assert aislamiento_linux.supervisar(str(request)) == 0
    output = (tmp_path / "request.json.supervisor").read_text(encoding="ascii")
    assert json.loads(output)["status"] == "cleanup_unverified"
    assert "PRIVATE-CLEANUP-CANARY" not in output
