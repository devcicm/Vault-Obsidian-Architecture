"""Linux invocation-owned subreaper; no process-global changes in the caller.

Session/group IDs do not define descendants. A dedicated subreaper adopts
orphans, freezes descendants before traversal, and signals stable pidfds. This
is lifetime control for trusted code, not a security or resource sandbox.

Known consequence: the supervisor starts its own session, so the worker has no
controlling terminal. Anything a tool spawns that prompts on `/dev/tty` (git
credential prompts, ssh passphrases) cannot ask interactively inside the
worker; configure non-interactive credentials (helpers, agents) instead.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import threading
import time

CLEANUP_SECONDS = 10.0


class LinuxContainmentError(RuntimeError):
    """No verified containment acknowledgment is available."""


def _stat(path):
    text = path.read_text(encoding="ascii")
    fields = text[text.rindex(")") + 2:].split()
    return fields[0], int(fields[1]), fields[19]  # state, parent, start ticks


def _children(pid):
    found = set()
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            found.update(int(value) for value in (task / "children").read_text().split())
        except FileNotFoundError:
            # A thread that exited cannot fork; its children are adopted.
            continue
    return found


def _prepare():
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise LinuxContainmentError("pidfd support is required")
    descriptor = os.pidfd_open(os.getpid())
    try:
        signal.pidfd_send_signal(descriptor, 0)
    finally:
        os.close(descriptor)
    # Kernels without CONFIG_PROC_CHILDREN expose no `children` files. Treating
    # that as "no descendants" would acknowledge cleanup that never happened.
    own = Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
    try:
        own.read_text()
    except OSError as exc:
        raise LinuxContainmentError("procfs descendant visibility is required") from exc
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                          ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise LinuxContainmentError("Cannot establish subreaper ownership")


def _exited(descriptor):
    return bool(select.select([descriptor], [], [], 0)[0])


def _reap():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if not pid:
            return


def _stop_tree():
    deadline = time.monotonic() + CLEANUP_SECONDS
    handles = {}

    def freeze(pid, parent):
        if pid in handles:
            if not _exited(handles[pid]):
                return
            os.close(handles.pop(pid))
        descriptor = None
        try:
            before = _stat(Path(f"/proc/{pid}/stat"))
            if before[1] != parent:
                return  # Reparented; the next root traversal will find it.
            descriptor = os.pidfd_open(pid)
            after = _stat(Path(f"/proc/{pid}/stat"))
            if before[2] != after[2] or after[1] != parent:
                os.close(descriptor)
                return
            handles[pid] = descriptor
            signal.pidfd_send_signal(descriptor, signal.SIGSTOP)
            while not _exited(descriptor):
                tasks = list(Path(f"/proc/{pid}/task").iterdir())
                states = []
                for task in tasks:
                    try:
                        states.append(_stat(task / "stat")[0])
                    except FileNotFoundError:
                        continue
                if states and all(state in "TtZX" for state in states):
                    break
                if time.monotonic() >= deadline:
                    raise LinuxContainmentError("A descendant could not be stopped")
                time.sleep(0.005)
            if not _exited(descriptor):
                for child in _children(pid):
                    freeze(child, pid)
        except (FileNotFoundError, ProcessLookupError):
            if descriptor is not None and pid not in handles:
                os.close(descriptor)

    try:
        while time.monotonic() < deadline:
            _reap()
            children = _children(os.getpid())
            if not children and all(_exited(fd) for fd in handles.values()):
                return
            for pid in children:
                freeze(pid, os.getpid())
            for descriptor in reversed(list(handles.values())):
                try:
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(0.005)
        raise LinuxContainmentError("Descendant quiescence could not be verified")
    finally:
        for descriptor in handles.values():
            try:
                if not _exited(descriptor):
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                os.close(descriptor)


def supervisar(request_path):
    """Acknowledge timeout only after every invocation-owned process is reaped."""
    request = Path(request_path)
    status = "unverified"
    worker = None
    try:
        data = json.loads(request.read_text(encoding="utf-8"))
        _prepare()
        if Path(str(request) + ".cancel").exists() or os.getppid() != data["caller_pid"]:
            status = "interrupted"
        elif time.monotonic() >= data["deadline"]:
            status = "timeout"
        else:
            worker = subprocess.Popen(data["worker_command"])
            Path(str(request) + ".admitted").touch()
            while True:
                # The supervisor runs in its own session, so a SIGTERM/SIGKILL
                # of the caller never reaches it. Reparenting means the caller
                # is gone and nobody will read the result: stop the tree now.
                if (Path(str(request) + ".cancel").exists()
                        or os.getppid() != data["caller_pid"]):
                    status = "interrupted"
                    break
                if time.monotonic() >= data["deadline"]:
                    status = "timeout"
                    break
                if worker.poll() is not None:
                    if worker.returncode == 0:
                        result = json.loads(Path(str(request) + ".result").read_text(encoding="ascii"))
                        if result.get("code") == 0:
                            status = "ok"
                        else:
                            status = "failed"
                    break
                time.sleep(0.01)
        if status != "ok":
            _stop_tree()
    except BaseException:
        status = "unverified"
        if worker is not None:
            try:
                _stop_tree()
            except BaseException:
                # Preserve the failed cleanup acknowledgment across the
                # process boundary. The caller must not claim quiescence.
                status = "cleanup_unverified"
    try:
        huerfano = os.getppid() != data["caller_pid"]
    except (NameError, KeyError, TypeError):
        huerfano = False
    if huerfano and status != "cleanup_unverified":
        # The caller died, so nobody reads the acknowledgment and its
        # TemporaryDirectory cleanup never runs: remove the private control
        # directory here, after the tree is verified quiescent.
        shutil.rmtree(request.parent, ignore_errors=True)
        return 0
    Path(str(request) + ".supervisor").write_text(json.dumps({"status": status}), encoding="ascii")
    return 0


def ejecutar(request, worker_command, env, deadline, supervisor_command):
    """Run `supervisor_command` (built by the caller, so this module imports
    nothing from it) as an invocation-owned subreaper for `worker_command`."""
    data = json.loads(request.read_text(encoding="utf-8"))
    data.update(worker_command=worker_command, deadline=deadline, caller_pid=os.getpid())
    request.write_text(json.dumps(data), encoding="utf-8")
    command = supervisor_command
    cancel = Path(str(request) + ".cancel")
    interrupts = []

    def on_interrupt(signum, frame):
        # Ctrl-C becomes a cancellation request, never an exception in this
        # wait: a second KeyboardInterrupt would kill the subreaper before it
        # acknowledges cleanup and orphan the tree it owns.
        interrupts.append(signum)
        cancel.touch()

    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGINT, on_interrupt)
    process = None
    try:
        process = subprocess.Popen(command, env=env, start_new_session=True)
        limit = time.monotonic() + max(0, deadline - time.monotonic()) + CLEANUP_SECONDS + 5
        cancelled_at = None
        while process.poll() is None:
            if interrupts and cancelled_at is None:
                cancelled_at = time.monotonic()
                limit = min(limit, cancelled_at + CLEANUP_SECONDS + 5)
            if time.monotonic() >= limit:
                # This is a failed supervisor, not a verified tool timeout.
                raise LinuxContainmentError("Supervisor acknowledgment was not received")
            time.sleep(0.01)
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
    interrupted = bool(interrupts)
    try:
        if process.returncode != 0:
            raise LinuxContainmentError("Supervisor failed")
        status = json.loads(Path(str(request) + ".supervisor").read_text(encoding="ascii"))["status"]
        if status == "timeout":
            raise subprocess.TimeoutExpired(worker_command, data["timeout"])
        if status == "interrupted":
            raise KeyboardInterrupt
        if status not in ("ok", "failed") or interrupted:
            raise LinuxContainmentError("Process containment could not be verified")
        result = json.loads(Path(str(request) + ".result").read_text(encoding="ascii"))
        if not (type(result["code"]) is int and isinstance(result["stdout"], str)
                and isinstance(result["stderr"], str)):
            raise LinuxContainmentError("Worker result could not be verified")
        return result
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise LinuxContainmentError("Supervisor result could not be verified") from exc
