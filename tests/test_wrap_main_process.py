"""Process-boundary guarantees for the public wrapper (A-06)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import vault_errors
from vault_io import set_vault_root
from apoyo import correr_python, esperar_condicion, lanzar_python, proceso_activo

PARENT_STATE = []


def change_memory():
    PARENT_STATE.append("child")
    print(json.dumps({"ok": True, "argv": sys.argv[1:]}))


def late_writer():
    root = Path(os.environ["WRAP_PROBE_DIR"])
    (root / "worker.pid").write_text(str(os.getpid()))
    esperar_condicion((root / "release").exists, timeout=30)
    (root / "late.txt").write_text("must not happen")


def descendant_writer():
    code = (
        "import os; from pathlib import Path; from apoyo import esperar_condicion; "
        "r=Path(os.environ['WRAP_PROBE_DIR']); "
        "(r/'descendant.pid').write_text(str(os.getpid())); "
        "assert esperar_condicion((r/'release').exists, timeout=30); "
        "(r/'late.txt').write_text('must not happen')"
    )
    lanzar_python("-c", code)
    late_writer()


def successful_background_job():
    code = (
        "import os; from pathlib import Path; from apoyo import esperar_condicion; "
        "r=Path(os.environ['WRAP_PROBE_DIR']); "
        "assert esperar_condicion((r/'release').exists, timeout=30); "
        "(r/'background.txt').write_text('completed')"
    )
    lanzar_python("-c", code, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL)
    print(json.dumps({"ok": True, "queued_async": True}))


def inherited_child_output():
    print("before", file=sys.stderr, flush=True)
    correr_python("-c",
                  "import sys; print('child output'); print('middle',file=sys.stderr)",
                  capture_output=False, check=True)
    print("after", file=sys.stderr, flush=True)
    print(json.dumps({"ok": True}))


@pytest.fixture
def probe(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("WRAP_PROBE_DIR", str(tmp_path))
    monkeypatch.setenv("VAULT_VOICE", "0")
    previous = set_vault_root(tmp_path)
    yield tmp_path
    set_vault_root(previous)


def test_callback_does_not_mutate_parent_memory(probe, capsys, monkeypatch):
    PARENT_STATE.clear()
    monkeypatch.setattr(sys, "argv", ["probe", "argument"])
    assert vault_errors.wrap_main(change_memory, "probe", timeout=15) == 0
    assert PARENT_STATE == []
    assert json.loads(capsys.readouterr().out)["argv"] == ["argument"]


def test_nonimportable_callback_is_rejected_without_execution(probe, capsys):
    changed = []
    assert vault_errors.wrap_main(lambda: changed.append(True), "probe") == 1
    assert changed == []
    assert json.loads(capsys.readouterr().out)["error_code"] == "INVALID_INPUT"


def test_child_stdout_does_not_corrupt_worker_protocol(probe, capfd):
    assert vault_errors.wrap_main(inherited_child_output, "probe", timeout=15) == 0
    output = capfd.readouterr()
    assert "child output" in output.out
    assert json.loads(output.out.strip().splitlines()[-1])["ok"] is True
    assert output.err.splitlines() == ["before", "middle", "after"]


def test_zero_budget_never_admits_callback(probe, capsys):
    assert vault_errors.wrap_main(late_writer, "probe", timeout=0) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "TOOL_TIMEOUT"
    assert not (probe / "worker.pid").exists()


def test_spawn_failure_is_sanitized_without_thread_fallback(probe, capsys, monkeypatch):
    from vault.kernel import aislamiento

    def failed(*args, **kwargs):
        raise OSError("private machine path must not leak")

    monkeypatch.setattr(aislamiento.subprocess, "Popen", failed)
    assert vault_errors.wrap_main(late_writer, "probe", timeout=5) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error_code"] == "UNEXPECTED_ERROR"
    assert "private machine path" not in output
    assert not (probe / "worker.pid").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job admission boundary")
def test_job_assignment_failure_never_admits_callback(probe, capsys, monkeypatch):
    from vault.kernel import aislamiento

    def denied(process):
        raise aislamiento.IsolationUnavailable("private path")

    monkeypatch.setattr(aislamiento, "_WindowsJob", denied)
    assert vault_errors.wrap_main(late_writer, "probe", timeout=5) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "UNEXPECTED_ERROR"
    assert not (probe / "worker.pid").exists()


def test_script_entry_preserves_stdin_stderr_and_large_output(probe):
    script = probe / "entry.py"
    script.write_text(
        "import sys,json,vault_errors\n"
        "def main():\n"
        "    value=sys.stdin.read()\n"
        "    print('diagnóstico',file=sys.stderr)\n"
        "    print(json.dumps({'ok':True,'input':value,'large':'x'*1000000}))\n"
        "if __name__=='__main__':\n"
        "    sys.exit(vault_errors.wrap_main(main,'probe',timeout=20))\n",
        encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path),
           "PYTHONIOENCODING": "utf-8"}
    result = correr_python(str(script), input="entrada ñ", env=env,
                           modo="text", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["input"] == "entrada ñ"
    assert len(payload["large"]) == 1000000
    assert result.stderr.strip() == "diagnóstico"


@pytest.mark.parametrize("callback", [late_writer, descendant_writer])
def test_timeout_stops_raw_writes_and_descendants(probe, capsys, callback):
    try:
        # The budget includes worker and descendant interpreter startup.
        assert vault_errors.wrap_main(callback, "probe", timeout=10) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == "TOOL_TIMEOUT"
        assert (probe / "worker.pid").exists(), "Callback must start for this probe"
        if callback is descendant_writer:
            assert (probe / "descendant.pid").exists()
    finally:
        # Also release the old threaded implementation on RED to avoid leaks.
        (probe / "release").touch()
    for marker in probe.glob("*.pid"):
        pid = int(marker.read_text(encoding="utf-8"))
        assert esperar_condicion(lambda pid=pid: not proceso_activo(pid), timeout=5), marker.name
    assert not (probe / "late.txt").exists()


def test_success_preserves_intentional_background_work(probe, capsys):
    try:
        assert vault_errors.wrap_main(successful_background_job, "probe", timeout=15) == 0
        assert json.loads(capsys.readouterr().out)["queued_async"] is True
    finally:
        (probe / "release").touch()
    assert esperar_condicion((probe / "background.txt").exists, timeout=5)
    assert (probe / "background.txt").read_text() == "completed"


def inherited_background_job():
    lanzar_python("-c",
                      "import os; from pathlib import Path; from apoyo import esperar_condicion; "
                      "root=Path(os.environ['WRAP_PROBE_DIR']); "
                      "assert esperar_condicion((root/'release').exists, timeout=30); "
                      "(root/'background.txt').write_text('completed')")
    print(json.dumps({"ok": True, "queued_async": True}))


def test_inherited_background_streams_do_not_extend_callback_deadline(probe, capsys):
    try:
        # The child remains alive until the wrapper returns: no startup-speed
        # assumption, and waiting for inherited pipe EOF still fails this probe.
        assert vault_errors.wrap_main(inherited_background_job, "probe", timeout=15) == 0
        assert json.loads(capsys.readouterr().out)["queued_async"] is True
        assert not (probe / "background.txt").exists()
    finally:
        (probe / "release").touch()
    assert esperar_condicion((probe / "background.txt").exists, timeout=8)
    assert (probe / "background.txt").read_text() == "completed"


def test_nested_top_level_script_callbacks_remain_importable(probe):
    script = probe / "nested.py"
    script.write_text(
        "import sys,json,vault_errors\n"
        "def inner():\n    print(json.dumps({'ok':True,'nested':True}))\n"
        "def outer():\n    return vault_errors.wrap_main(inner,'inner',timeout=10)\n"
        "if __name__=='__main__':\n"
        "    sys.exit(vault_errors.wrap_main(outer,'outer',timeout=15))\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path), "PYTHONIOENCODING": "utf-8"}
    result = correr_python(str(script), env=env, modo="text", timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["nested"] is True


def session_escape_writer():
    code = (
        "import os; from pathlib import Path; from apoyo import esperar_condicion; os.setsid(); "
        "r=Path(os.environ['WRAP_PROBE_DIR']); "
        "(r/'escaped.pid').write_text(str(os.getpid())); "
        "assert esperar_condicion((r/'release').exists, timeout=30); "
        "(r/'escaped-write.txt').write_text('late')"
    )
    lanzar_python("-c", code)
    late_writer()


def nested_session_escape_writer():
    Path(os.environ["WRAP_PROBE_DIR"], "outer.pid").write_text(str(os.getpid()))
    return vault_errors.wrap_main(session_escape_writer, "inner", timeout=30)


def threaded_session_escape_writer():
    import threading
    threading.Thread(target=session_escape_writer).start()
    esperar_condicion(lambda: False, timeout=30)


def orphan_session_escape_writer():
    code = (
        "import os\nfrom pathlib import Path\nfrom apoyo import esperar_condicion\n"
        "if os.fork(): os._exit(0)\n"
        "os.setsid()\nr=Path(os.environ['WRAP_PROBE_DIR'])\n"
        "(r/'escaped.pid').write_text(str(os.getpid()))\n"
        "assert esperar_condicion((r/'release').exists, timeout=30)\n"
        "(r/'escaped-write.txt').write_text('late')\n"
    )
    lanzar_python("-c", code)
    late_writer()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper containment")
@pytest.mark.parametrize("callback", [session_escape_writer, nested_session_escape_writer,
                                      threaded_session_escape_writer, orphan_session_escape_writer])
def test_linux_timeout_contains_sessions_and_nested_workers(probe, capsys, callback):
    try:
        assert vault_errors.wrap_main(callback, "outer", timeout=12) == 1
        assert json.loads(capsys.readouterr().out)["error_code"] == "TOOL_TIMEOUT"
        assert (probe / "escaped.pid").exists(), "Escaped child must start before timeout"
    finally:
        (probe / "release").touch()
    for marker in probe.glob("*.pid"):
        pid = int(marker.read_text(encoding="utf-8"))
        assert esperar_condicion(lambda pid=pid: not proceso_activo(pid), timeout=5), marker.name
    assert not (probe / "escaped-write.txt").exists()
    for marker in probe.glob("*.pid"):
        assert not Path("/proc", marker.read_text()).exists(), marker.name


@pytest.mark.skipif(sys.platform != "linux", reason="Linux capability admission")
def test_linux_unavailable_containment_fails_before_callback(probe, capsys, monkeypatch):
    from vault.kernel import aislamiento
    original = aislamiento.subprocess.Popen

    def without_capability(command, *args, **kwargs):
        if "aislamiento_linux import supervisar" in command[2]:
            command = list(command)
            command[2] = command[2].replace(
                " code = entry(sys.argv[1])",
                " import vault.kernel.aislamiento_linux as probe\n"
                " def unavailable(): raise OSError('private capability canary')\n"
                " probe._prepare=unavailable\n code = entry(sys.argv[1])")
            assert "private capability canary" in command[2], "Injection must reach the supervisor"
        return original(command, *args, **kwargs)

    monkeypatch.setattr(aislamiento.subprocess, "Popen", without_capability)
    assert vault_errors.wrap_main(late_writer, "probe", timeout=5) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error_code"] == "UNEXPECTED_ERROR"
    assert "private capability canary" not in output
    assert not (probe / "worker.pid").exists()


def report_pythonpath():
    print(json.dumps({"ok": True, "pythonpath": os.environ.get("PYTHONPATH")}))


def entry_returning_zero(payload):
    return 0


def test_caller_cwd_cannot_shadow_worker_imports(probe, capsys, monkeypatch):
    """`python -c` puts the cwd first on sys.path; a cwd `vault/` must not win."""
    project = probe / "project"
    (project / "vault").mkdir(parents=True)
    (project / "vault" / "__init__.py").write_text("raise ImportError('cwd shadow')\n")
    (project / "json.py").write_text("raise ImportError('cwd shadow')\n")
    monkeypatch.chdir(project)
    assert vault_errors.wrap_main(change_memory, "probe", timeout=30) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_descendants_inherit_caller_pythonpath_unchanged(probe, capsys, monkeypatch):
    sentinel = str(probe / "caller-pythonpath")
    monkeypatch.setenv("PYTHONPATH", sentinel)
    assert vault_errors.wrap_main(report_pythonpath, "probe", timeout=30) == 0
    assert json.loads(capsys.readouterr().out)["pythonpath"] == sentinel


def test_unserializable_arguments_are_sanitized(probe, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["probe", object()])
    assert vault_errors.wrap_main(late_writer, "probe", timeout=30) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "UNEXPECTED_ERROR"
    assert not (probe / "worker.pid").exists()


def test_missing_caller_stderr_does_not_break_isolation(probe, monkeypatch):
    from vault.kernel.aislamiento import ejecutar_aislado
    monkeypatch.setattr(sys, "stderr", None)
    assert ejecutar_aislado(__name__, "entry_returning_zero", {}, 30)["code"] == 0


def _outer_wrap_main(probe, timeout, tmpdir=None):
    from apoyo import entorno
    code = ("import sys, test_wrap_main_process as t, vault_errors; "
            f"sys.exit(vault_errors.wrap_main(t.late_writer, 'probe', timeout={timeout}))")
    env = entorno(probe)
    if tmpdir is not None:
        env.update(TMPDIR=str(tmpdir), TEMP=str(tmpdir), TMP=str(tmpdir))
    return lanzar_python("-c", code, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux supervisor runs in its own session")
def test_linux_caller_death_stops_the_tree(probe):
    import signal
    tmpdir = probe / "caller-tmp"
    tmpdir.mkdir()
    outer = _outer_wrap_main(probe, 120, tmpdir=tmpdir)
    try:
        assert esperar_condicion((probe / "worker.pid").exists, timeout=60), "Callback must start"
        assert list(tmpdir.glob("vault-process-*")), "the private control directory must exist"
        worker = int((probe / "worker.pid").read_text())
        outer.send_signal(signal.SIGKILL)
        outer.communicate(timeout=30)
        assert esperar_condicion(lambda: not proceso_activo(worker), timeout=15)
        # Nobody runs the dead caller's TemporaryDirectory cleanup: the supervisor does.
        assert esperar_condicion(lambda: not list(tmpdir.glob("vault-process-*")), timeout=15)
    finally:
        (probe / "release").touch()
    assert not (probe / "late.txt").exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux supervisor runs in its own session")
def test_linux_repeated_interrupt_never_orphans_the_tree(probe):
    import signal
    outer = _outer_wrap_main(probe, 120)
    try:
        assert esperar_condicion((probe / "worker.pid").exists, timeout=60), "Callback must start"
        worker = int((probe / "worker.pid").read_text())
        for _ in range(5):
            outer.send_signal(signal.SIGINT)
        stdout, _ = outer.communicate(timeout=60)
        assert outer.returncode == 130, stdout
        assert json.loads(stdout.strip().splitlines()[-1])["error_code"] == "INTERRUPTED"
        assert not proceso_activo(worker)
    finally:
        (probe / "release").touch()
    assert not (probe / "late.txt").exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux procfs admission")
def test_linux_missing_procfs_children_fails_closed(probe, capsys, monkeypatch):
    from vault.kernel import aislamiento
    original = aislamiento.subprocess.Popen

    def without_children(command, *args, **kwargs):
        if "aislamiento_linux import supervisar" in command[2]:
            command = list(command)
            command[2] = command[2].replace(
                " code = entry(sys.argv[1])",
                " import pathlib\n"
                " read = pathlib.Path.read_text\n"
                " def hidden(self, *a, **k):\n"
                "  if self.name == 'children': raise FileNotFoundError(self.name)\n"
                "  return read(self, *a, **k)\n"
                " pathlib.Path.read_text = hidden\n code = entry(sys.argv[1])")
            assert "def hidden" in command[2], "Injection must reach the supervisor"
        return original(command, *args, **kwargs)

    monkeypatch.setattr(aislamiento.subprocess, "Popen", without_children)
    try:
        assert vault_errors.wrap_main(late_writer, "probe", timeout=5) == 1
        assert json.loads(capsys.readouterr().out)["error_code"] == "UNEXPECTED_ERROR"
        assert not (probe / "worker.pid").exists()
    finally:
        (probe / "release").touch()


_SITECUSTOMIZE_ESCAPISTA = '''
import os, subprocess, sys
if os.environ.get("WRAP_STARTUP_PROBE") and not os.environ.get("WRAP_STARTUP_CHILD"):
    env = dict(os.environ, WRAP_STARTUP_CHILD="1")
    code = ("import os, time, pathlib; p = pathlib.Path(os.environ['WRAP_STARTUP_PROBE']); "
            "(p / 'startup-child.pid').write_text(str(os.getpid())); time.sleep(60)")
    subprocess.Popen([sys.executable, "-c", code], env=env)
'''


@pytest.mark.skipif(os.name != "nt", reason="Windows Job admission boundary")
def test_interpreter_startup_runs_inside_the_job(probe, capsys, monkeypatch):
    """A process started during worker startup (site hooks) must die with the tree (A7)."""
    hooks = probe / "hooks"
    hooks.mkdir()
    (hooks / "sitecustomize.py").write_text(_SITECUSTOMIZE_ESCAPISTA, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(hooks))
    monkeypatch.setenv("WRAP_STARTUP_PROBE", str(probe))
    try:
        assert vault_errors.wrap_main(late_writer, "probe", timeout=10) == 1
        assert json.loads(capsys.readouterr().out)["error_code"] == "TOOL_TIMEOUT"
        marker = probe / "startup-child.pid"
        assert esperar_condicion(marker.exists, timeout=10), "the startup hook must run"
        child = int(marker.read_text(encoding="utf-8"))
        assert esperar_condicion(lambda: not proceso_activo(child), timeout=10), \
            "a process started before admission escaped the Job"
    finally:
        (probe / "release").touch()
