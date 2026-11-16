# macOS process containment: reference plan

Status: **reference only, not implemented.** macOS is out of scope (no CI runner, no
`Operating System :: MacOS` classifier). Since A-06, every tool that runs through
`wrap_main` fails closed on macOS with `UNEXPECTED_ERROR`, because
`vault.kernel.aislamiento.ejecutar_aislado` has no verified containment adapter for the
platform. This document records how an adapter could be built if macOS is ever promised.

## Contract the adapter must meet

The same contract as the Windows and Linux adapters (`vault/kernel/aislamiento.py`,
`vault/kernel/aislamiento_linux.py`):

1. Admission before execution: no callback module is imported until containment is
   established; unavailable containment fails closed before the callback runs.
2. Timeout and interruption stop every invocation-owned process, including descendants
   that start a new session or process group, before `wrap_main` returns.
3. A successful tool may leave intentional background work running (release, not kill).
4. The caller's death stops the tree; nobody else reads the result.
5. Cleanup is acknowledged; an unverified cleanup is never reported as stopped.

## Why the existing adapters do not port

- **Windows Job objects** (kill-on-close, active-process accounting) have no macOS
  equivalent.
- **Linux subreaper** (`PR_SET_CHILD_SUBREAPER`), `pidfd` and `/proc/<pid>/task/*/children`
  do not exist on macOS. Orphans are re-parented to `launchd`, so a supervisor loses
  them once their parent exits.

## Proposed design

- **Supervisor process** started with `start_new_session=True`, like Linux, watching the
  caller with `kqueue` `EVFILT_PROC` / `NOTE_EXIT` on the caller PID instead of polling
  `getppid()`.
- **Descendant tracking while they are still attached:** enumerate children with
  `libproc` `proc_listchildpids` (via `ctypes`) on a short cadence, recursively, and record
  `(pid, start time)` from `proc_pidinfo(PROC_PIDTBSDINFO)` so a reused PID is never
  signalled. A descendant that daemonizes between two polls escapes: this is the known
  limit, and it must be stated in the envelope, not hidden.
- **Freeze then kill:** `SIGSTOP` every tracked process top-down, re-enumerate until the
  set is stable, then `SIGKILL` and `waitpid`/`kqueue` until each identity is gone.
- **Fail closed** when `libproc` or `kqueue` are unavailable or return errors.
- **Optional stronger boundary:** run the worker under a dedicated user or `sandbox-exec`
  profile so escaped descendants cannot write the vault. Not a lifetime guarantee; a
  security boundary would need a separate decision.

## Required delivery steps (when promised)

1. Add `macos-latest` to `.github/workflows/vault-ci.yml` (`validate` and
   `product-gates`) and the `Operating System :: MacOS` classifier together, so
   `vault_produccion --check` keeps promise and runner in sync.
2. Implement `vault/kernel/aislamiento_macos.py` with the contract above; select it in
   `ejecutar_aislado` only on `sys.platform == "darwin"`.
3. Port the tests: mirror `tests/test_wrap_main_process.py` (timeout, descendants,
   background release, nested wrap_main, caller death, repeated interrupt) and
   `tests/test_wrap_main_linux_invariants.py` (nested sessions, PID reuse, failed cleanup
   acknowledgment) with `darwin` markers.
4. Document the daemonize-between-polls limit in `README.md` and in the TOOL_TIMEOUT
   envelope wording for macOS.

## Acceptance criteria

- All ported tests pass on `macos-latest` for Python 3.9 and 3.12.
- No descendant survives a timeout in 100 repeated runs of the nested-session probe.
- `wrap_main` never reports `INTERRUPTED`/`TOOL_TIMEOUT` with "has stopped" when the
  cleanup acknowledgment is unverified.
