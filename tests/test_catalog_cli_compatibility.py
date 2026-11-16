"""Public catalog CLI must retain the unwrapped main contract."""
import os
import json
import re
from pathlib import Path

import pytest
from apoyo import correr_python, esperar_condicion, proceso_activo

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vault_mcp_catalog.py"
DIRECT = (
    "import runpy,sys; p=sys.argv.pop(1); "
    "sys.path.insert(0,str(__import__('pathlib').Path(p).parent)); "
    "sys.argv[0]=p; runpy.run_path(p,run_name='catalog_contract')['main']()"
)


@pytest.mark.parametrize("encoding", [None, "utf-8"])
@pytest.mark.parametrize("args", [
    ["--stats"], ["--help"], ["--check"], ["--check-params"],
    ["--check-contracts", "--spec", "absent.json"], ["--invalid"],
    ["--sync", "--output", "catalog.json"],
])
def test_cli_preserves_main_bytes_exit_and_files(tmp_path, encoding, args):
    env = {**os.environ, "VAULT_ROOT": str(tmp_path / "absent-vault"),
           "VAULT_TOOL_TIMEOUT": "60", "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONIOENCODING", None)
    if encoding:
        env["PYTHONIOENCODING"] = encoding

    def snapshot():
        return {str(p.relative_to(tmp_path)): p.read_bytes()
                for p in tmp_path.rglob("*") if p.is_file()}

    baseline = correr_python("-c", DIRECT, str(SCRIPT), *args, cwd=tmp_path,
                             env=env, modo="bytes", timeout=90)
    before = snapshot()
    candidate = correr_python(str(SCRIPT), *args, cwd=tmp_path, env=env,
                              modo="bytes", timeout=90)
    def stable_output(value):
        # Error envelopes timestamp each invocation; preserve every other byte,
        # including the timestamp key, whitespace, encoding and line endings.
        return re.sub(rb'("timestamp": ")[^"\r\n]+(")', rb'\1<CLOCK>\2', value)

    assert (candidate.returncode, stable_output(candidate.stdout), candidate.stderr) == (
        baseline.returncode, stable_output(baseline.stdout), baseline.stderr)
    assert snapshot() == before


def test_timeout_reaps_worker_before_return(tmp_path):
    # A real slow worker, not a mocked timeout or merely a zero-second budget.
    script = tmp_path / "slow_catalog.py"
    late = tmp_path / "late-write"
    started = tmp_path / "started"
    source = SCRIPT.read_text(encoding="utf-8").replace(
        'if __name__ == "__catalog_worker__":\n    main()',
        'if __name__ == "__catalog_worker__":\n'
        f'    Path({str(started)!r}).write_text(str(__import__("os").getpid()))\n'
        '    from apoyo import esperar_condicion\n'
        '    esperar_condicion(lambda: False, timeout=30)\n'
        f'    Path({str(late)!r}).write_text("late")\n    main()',
    )
    script.write_text(source, encoding="utf-8")
    root = tmp_path / "vault"
    (root / "00_System").mkdir(parents=True)
    env = {**os.environ, "VAULT_ROOT": str(root), "VAULT_TOOL_TIMEOUT": "1",
           "PYTHONPATH": os.pathsep.join([str(ROOT / "scripts"), str(ROOT)])}
    result = correr_python(str(script), "--stats", cwd=tmp_path, env=env,
                           modo="bytes", timeout=30)
    assert started.exists(), "The worker must actually start before the deadline"
    assert result.returncode == 1
    assert json.loads(result.stdout)["error_code"] == "TOOL_TIMEOUT"
    assert str(tmp_path).encode() not in result.stdout
    trace = (root / "00_System" / ".tool-trace.json").read_text(encoding="utf-8")
    assert "TOOL_TIMEOUT" in trace
    pid = int(started.read_text(encoding="utf-8"))
    assert esperar_condicion(lambda: not proceso_activo(pid), timeout=10), (
        "The timed-out worker must be gone before checking for late writes"
    )
    assert not late.exists()


def test_worker_preserves_parent_stream_configuration(tmp_path):
    # Windows consoles use UTF-8 even when a redirected child chooses cp1252.
    # Explicit stream configuration reproduces that boundary without ConPTY.
    env = {**os.environ, "VAULT_ROOT": str(tmp_path / "absent"),
           "VAULT_TOOL_TIMEOUT": "60"}
    env.pop("PYTHONIOENCODING", None)
    prefix = (
        "import runpy,sys; p=sys.argv.pop(1); "
        "sys.path.insert(0,str(__import__('pathlib').Path(p).parent)); "
        "sys.argv[0]=p; "
        "sys.stdout.reconfigure(encoding='utf-8',errors='strict'); "
        "sys.stderr.reconfigure(encoding='ascii',errors='backslashreplace'); "
        "m=runpy.run_path(p,run_name='catalog_contract'); "
    )
    results = [correr_python(
        "-X", "utf8=0", "-c", prefix + f"sys.exit(m[{entry!r}]())",
        str(SCRIPT), "--stats", cwd=tmp_path, env=env, modo="bytes", timeout=90,
    ) for entry in ("main", "_run_cli")]
    assert results[0].returncode == results[1].returncode == 0
    assert results[0].stdout == results[1].stdout
    assert results[0].stderr == results[1].stderr
