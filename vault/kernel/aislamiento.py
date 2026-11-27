"""Bounded subprocess execution with admission and descendant containment.

This is a lifetime boundary, not a security sandbox. The callback is trusted
local code. No vault modules are imported and no vault paths are written here.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


class IsolationUnavailable(RuntimeError):
    """The worker could not be safely admitted or its completion verified."""

    def __init__(self, message: str = "", *, public_reason: str = "") -> None:
        super().__init__(message)
        self.public_reason = public_reason


def bootstrap_command(entry_module: str, entry_function: str, request: Path) -> list:
    """Interpreter command whose import path is exactly the caller's sys.path.

    `python -c` prepends the current directory to sys.path, so a `vault/`,
    `json.py` or `yaml.py` in the caller's cwd would shadow the toolkit inside
    the worker. The cwd entry is dropped before any import, and the caller's
    sys.path travels in the request file instead of PYTHONPATH so that
    descendants of the worker inherit the caller's environment unchanged.
    """
    code = (
        "import sys\n"
        "getattr(sys.flags, 'safe_path', False) or sys.path.pop(0)\n"
        "try:\n"
        " import json\n"
        " with open(sys.argv[1], encoding='utf-8') as handle:\n"
        "  sys.path[:] = json.load(handle)['sys_path']\n"
        f" from {entry_module} import {entry_function} as entry\n"
        " code = entry(sys.argv[1])\n"
        "except BaseException:\n"
        " code = 1\n"
        "sys.exit(code)"
    )
    return [sys.executable, "-c", code, str(request)]


class _WindowsJob:
    """A non-inheritable kill-on-close Job, assigned before admission."""

    def __init__(self, process):
        import ctypes as c
        from ctypes import wintypes as w

        class BasicLimits(c.Structure):
            _fields_ = [("process_time", c.c_longlong), ("job_time", c.c_longlong),
                        ("flags", w.DWORD), ("min_ws", c.c_size_t),
                        ("max_ws", c.c_size_t), ("active_limit", w.DWORD),
                        ("affinity", c.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class IoCounters(c.Structure):
            _fields_ = [(name, c.c_ulonglong) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes",
                         "write_bytes", "other_bytes")]

        class Limits(c.Structure):
            _fields_ = [("basic", BasicLimits), ("io", IoCounters),
                        ("process_memory", c.c_size_t), ("job_memory", c.c_size_t),
                        ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]

        class Accounting(c.Structure):
            _fields_ = [(name, c.c_longlong) for name in
                        ("user", "kernel", "period_user", "period_kernel")] + [
                        (name, w.DWORD) for name in
                        ("faults", "total", "active", "terminated")]

        api = c.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateJobObjectW", [c.c_void_p, w.LPCWSTR], w.HANDLE),
            ("SetInformationJobObject", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
            ("TerminateJobObject", [w.HANDLE, w.UINT], w.BOOL),
            ("QueryInformationJobObject", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
            ("CloseHandle", [w.HANDLE], w.BOOL),
        ):
            fn = getattr(api, name)
            fn.argtypes, fn.restype = args, result
        self.api, self.c, self.Accounting, self.Limits = api, c, Accounting, Limits
        self.handle = api.CreateJobObjectW(None, None)
        if not self.handle:
            raise IsolationUnavailable("Cannot create process containment")
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits)):
            api.CloseHandle(self.handle)
            raise IsolationUnavailable("Cannot configure process containment")
        if not api.AssignProcessToJobObject(self.handle, int(process._handle)):
            api.CloseHandle(self.handle)
            raise IsolationUnavailable("Cannot admit worker to process containment")

    def release(self):
        """Successful tools may deliberately leave asynchronous work running."""
        limits = self.Limits()
        if not self.api.SetInformationJobObject(
            self.handle, 9, self.c.byref(limits), self.c.sizeof(limits)
        ):
            self.stop()
            raise IsolationUnavailable("Cannot release completed process containment")
        self.api.CloseHandle(self.handle)

    def stop(self):
        try:
            if not self.api.TerminateJobObject(self.handle, 1):
                raise IsolationUnavailable("Cannot terminate process containment")
            deadline = time.monotonic() + 10
            while True:
                state = self.Accounting()
                if not self.api.QueryInformationJobObject(
                    self.handle, 1, self.c.byref(state), self.c.sizeof(state), None
                ):
                    raise IsolationUnavailable("Cannot verify process containment")
                if not state.active:
                    break
                if time.monotonic() >= deadline:
                    raise IsolationUnavailable("Process containment did not become quiescent")
                time.sleep(0.01)
        finally:
            self.api.CloseHandle(self.handle)


def _worker(request_path: str):
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    # No callback module is imported until the parent has assigned containment.
    # A parent that dies before admission must not leave this loop spinning.
    admission_deadline = time.monotonic() + max(float(request["timeout"]), 0) + 5
    while not Path(request_path + ".admitted").exists():
        if time.monotonic() >= admission_deadline:
            return 1
        time.sleep(0.01)
    stdout = io.StringIO()
    sys.stderr.reconfigure(encoding=request["stderr_encoding"],
                           errors=request["stderr_errors"])
    # Keep Python stderr and inherited child stderr on the same descriptor so
    # their ordering is preserved. Only the wrapper's stdout is text-captured.
    try:
        with contextlib.redirect_stdout(stdout):
            module = importlib.import_module(request["module"])
            code = getattr(module, request["function"])(request["payload"])
    except BaseException:
        # Unexpected bootstrap failures must not expose local tracebacks.
        return 1
    # Inherited child file descriptors can write directly to stdout. Keep the
    # control result separate so that legitimate streamed output is not JSON.
    Path(request_path + ".result").write_text(
        json.dumps({"code": code, "stdout": stdout.getvalue(),
                    "stderr": ""}, ensure_ascii=True), encoding="ascii")
    return 0


def ejecutar_aislado(module: str, function: str, payload: dict, timeout: float) -> dict:
    """Invoke an importable entrypoint; stop its tree on failure or timeout.

    OS streams are inherited; control results use a private temporary file.
    Waiting for the worker (not descendant-held pipe EOF) preserves successful
    background launches. The budget includes worker startup. All
    exceptional paths revoke admission/terminate the worker without fallback.
    """
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vault-process-") as directory:
        request = Path(directory) / "request.json"
        stderr = sys.stderr
        try:
            request.write_text(json.dumps({
                "module": module, "function": function, "payload": payload,
                "timeout": timeout,
                # Only the cwd entry ("") is made absolute; other entries, including
                # path-hook placeholders of editable installs, travel unchanged.
                "sys_path": [p if p else str(Path(os.getcwd()).resolve()) for p in sys.path],
                "stderr_encoding": getattr(stderr, "encoding", None) or "utf-8",
                "stderr_errors": getattr(stderr, "errors", None) or "backslashreplace"}),
                encoding="utf-8")
        except (TypeError, ValueError) as exc:
            raise IsolationUnavailable("Callback arguments cannot cross the process boundary") from exc
        env = dict(os.environ)
        command = bootstrap_command("vault.kernel.aislamiento", "_worker", request)
        if sys.platform == "linux":
            from .aislamiento_linux import ejecutar, LinuxContainmentError
            try:
                supervisor = bootstrap_command("vault.kernel.aislamiento_linux", "supervisar", request)
                return ejecutar(request, command, env, started + timeout, supervisor)
            except LinuxContainmentError as exc:
                raise IsolationUnavailable(
                    "Linux containment could not be verified",
                    public_reason=str(exc),
                ) from exc
        if os.name != "nt":
            raise IsolationUnavailable("No verified containment adapter for this platform")
        process, job, completed = None, None, False
        try:
            process = subprocess.Popen(command, env=env)
            if os.name == "nt":
                job = _WindowsJob(process)
            remaining = max(0, timeout - (time.monotonic() - started))
            if not remaining:
                raise subprocess.TimeoutExpired(command, timeout)
            Path(str(request) + ".admitted").touch()
            process.wait(timeout=remaining)
            if process.returncode != 0:
                raise IsolationUnavailable("Worker failed before publishing its result")
            try:
                result = json.loads(Path(str(request) + ".result").read_text(encoding="ascii"))
                if not (isinstance(result["code"], int) and isinstance(result["stdout"], str)
                        and isinstance(result["stderr"], str)):
                    raise ValueError("Invalid worker result")
            except (ValueError, KeyError, TypeError) as exc:
                raise IsolationUnavailable("Worker result could not be verified") from exc
            completed = result["code"] == 0
        finally:
            if process is not None:
                try:
                    if job is not None:
                        job.release() if completed else job.stop()
                    elif process.poll() is None:
                        process.kill()  # No callback was admitted when assignment failed.
                finally:
                    process.wait()
        return result
