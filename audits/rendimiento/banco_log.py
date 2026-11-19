#!/usr/bin/env python3
"""Bench: the cost of ONE more logged operation as the change log grows.

The question it answers (S5 of `odd/tasks/bigo-inmutabilidad.md`): does the
cost of an operation that writes a change-log row depend on how many rows the
vault already holds (`h`)? Before the append-only log it did: every row read the
whole `00_System/.change-log.json`, appended one entry, rewrote it, and did the
same with `00_System/change-log.md`.

For each `h` in `--h` it builds a scratch vault (one `vault_init`, copied), seeds
`h` existing rows, and measures `--reps` consecutive operations of each kind:

- `change_log`: `vault_change_log --action created ...`
- `vault_write`: `vault_write` creating one note (which logs one row).

Seeding scenarios:

- `legacy`: the rows live in the frozen JSON array (`.change-log.json`, the
  format every vault had before the append-only log) and in the Markdown table.
  This is the only scenario a toolkit without the append-only log has.
- `lines`: the rows live in the append-only `.change-log.jsonl`, written in the
  owner's own line format. Only when the checked-out toolkit has it.

Each operation runs its tool's `main()` in this interpreter through the
product executor (`vault.ejecutor.ejecutar`, without the `wrap_main` envelope,
whose cost does not depend on the log), after a warm-up in a separate vault so imports are not measured. Wall time is
`time.perf_counter`; bytes read/written are the process I/O counters around the
single operation (Windows `GetProcessIoCounters`, Linux `/proc/self/io`), so they
include every file the operation touched, not only the log. The median of the
repetitions is reported.

No network, scratch only: every vault is created under `--scratch` (default a
new temporary directory) and nothing in the repository is written.

    python audits/rendimiento/banco_log.py --h 0,1000,10000,50000 --reps 5
    python audits/rendimiento/banco_log.py --json out.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
for _p in (str(REPO), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MD_HEADER = (
    "# Change Log\n\n"
    "Registro automatico de cambios en el vault.\n\n"
    "| Timestamp | Action | Path | New Path | Reason | Agent |\n"
    "|---|---|---|---|---|---|\n"
)


# ── process I/O counters ─────────────────────────────────────────────────────

def _io_counters() -> Optional[Dict[str, int]]:
    """Bytes read and written by this process so far, or None when unknown."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        counters = IO_COUNTERS()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO_COUNTERS)]
        if not kernel32.GetProcessIoCounters(kernel32.GetCurrentProcess(), ctypes.byref(counters)):
            return None
        return {"read": int(counters.ReadTransferCount), "written": int(counters.WriteTransferCount)}
    try:
        campos = dict(line.split(": ") for line in Path("/proc/self/io").read_text().splitlines())
        return {"read": int(campos["rchar"]), "written": int(campos["wchar"])}
    except (OSError, KeyError, ValueError):
        return None


# ── scratch vaults ───────────────────────────────────────────────────────────

def _run_tool(root: Path, argv: List[str]) -> Dict[str, Any]:
    """One tool run in this interpreter, CLI envelope; stdout is captured."""
    from vault.ejecutor import ejecutar

    # Without `wrap_main`: the envelope wrapper re-runs the tool where this
    # process' I/O counters do not see it, and its cost (trace, voice) does
    # not depend on the log size. The tool's own `main()` is what is measured.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        corrida = ejecutar(None, argv, raiz=root, agente="bench")
    try:
        envelope = json.loads(corrida.texto[corrida.texto.index("{"):])
    except ValueError:
        envelope = {"ok": False, "raw": corrida.texto[-300:]}
    return {"code": corrida.codigo, "envelope": envelope}


def _template(scratch: Path) -> Path:
    root = scratch / "template"
    root.mkdir(parents=True, exist_ok=True)
    result = _run_tool(root, ["vault_init.py", "--no-audit"])
    if result["code"] != 0:
        raise SystemExit(f"vault_init failed: {result['envelope']}")
    return root


def _entries(h: int) -> List[Dict[str, Any]]:
    return [{
        "id": str(uuid.UUID(int=i + 1)),
        "action": "created",
        "path": f"07_Knowledge/seed-{i:06d}.md",
        "new_path": None,
        "reason": f"seed row {i}",
        "agent": "bench",
        "timestamp": "2026-01-01T00:00:00.000Z",
    } for i in range(h)]


def _md_rows(entries: List[Dict[str, Any]]) -> str:
    return "".join(
        f"| {e['timestamp'][:19]} | `{e['action']}` | `{e['path']}` | `` | {e['reason']} | {e['agent']} |\n"
        for e in entries)


def _lines_supported() -> bool:
    from vault.gobernanza.repositorio import RepositorioGobernanza

    return hasattr(RepositorioGobernanza, "bitacora_cambios_lineas")


def _seed(root: Path, h: int, scenario: str) -> None:
    system = root / "00_System"
    system.mkdir(parents=True, exist_ok=True)
    entries = _entries(h)
    if h:
        # write_bytes, not write_text(newline=): the Python 3.9 floor.
        (system / "change-log.md").write_bytes((MD_HEADER + _md_rows(entries)).encode("utf-8"))
    if scenario == "legacy":
        if h:
            # The exact pre-append-only format: one JSON array, indent 2.
            (system / ".change-log.json").write_bytes(
                json.dumps(entries, indent=2, ensure_ascii=False).encode("utf-8"))
    else:
        from vault.gobernanza.repositorio import RepositorioGobernanza
        from vault.kernel import construir

        destino = RepositorioGobernanza(construir(root)).bitacora_cambios_lineas
        if h:
            # The owner's line format, written in one pass (seeding, not measuring).
            destino.write_bytes("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                        for e in entries).encode("utf-8"))


# ── operations ───────────────────────────────────────────────────────────────

def _op_change_log(root: Path, k: int) -> List[str]:
    return ["vault_change_log.py", "--action", "created", "--path", f"07_Knowledge/bench-{k}.md",
            "--reason", f"bench op {k}", "--agent", "bench"]


def _op_vault_write(root: Path, k: int) -> List[str]:
    return ["vault_write.py", "--folder", "07_Knowledge", "--title", f"Bench note {k:04d}",
            "--tags", "bench", "--content",
            f"Bench note {k} first line.\n\nA second paragraph with context.\n\nA third one."]


OPERATIONS: Dict[str, Callable[[Path, int], List[str]]] = {
    "change_log": _op_change_log,
    "vault_write": _op_vault_write,
}


def _measure(root: Path, op: str, reps: int) -> Dict[str, Any]:
    walls: List[float] = []
    reads: List[int] = []
    writes: List[int] = []
    failures = 0
    for k in range(reps):
        argv = OPERATIONS[op](root, k)
        before = _io_counters()
        start = time.perf_counter()
        result = _run_tool(root, argv)
        wall = time.perf_counter() - start
        after = _io_counters()
        if result["code"] != 0 or not result["envelope"].get("ok"):
            failures += 1
        walls.append(wall)
        if before and after:
            reads.append(after["read"] - before["read"])
            writes.append(after["written"] - before["written"])
    return {
        "wall_s": round(statistics.median(walls), 4),
        "read_bytes": int(statistics.median(reads)) if reads else None,
        "written_bytes": int(statistics.median(writes)) if writes else None,
        "failures": failures,
    }


def bench(hs: List[int], reps: int, scratch: Path) -> Dict[str, Any]:
    template = _template(scratch)
    # Warm-up in its own vault: imports and first-use caches are not measured.
    warm = scratch / "warm"
    shutil.copytree(template, warm)
    for op in OPERATIONS:
        _run_tool(warm, OPERATIONS[op](warm, 999))
    scenarios = ["legacy"] + (["lines"] if _lines_supported() else [])
    rows: List[Dict[str, Any]] = []
    for scenario in scenarios:
        for h in hs:
            for op in OPERATIONS:
                root = scratch / f"{scenario}-{h}-{op}"
                shutil.copytree(template, root)
                _seed(root, h, scenario)
                rows.append({"scenario": scenario, "h": h, "op": op, **_measure(root, op, reps)})
                shutil.rmtree(root, ignore_errors=True)
    return {"lines_supported": _lines_supported(), "reps": reps, "rows": rows}


def _table(result: Dict[str, Any]) -> str:
    out = ["| scenario | h | op | wall s (median) | read bytes | written bytes | failures |",
           "|---|---:|---|---:|---:|---:|---:|"]
    for r in result["rows"]:
        out.append(f"| {r['scenario']} | {r['h']} | {r['op']} | {r['wall_s']} | "
                   f"{r['read_bytes']} | {r['written_bytes']} | {r['failures']} |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--h", default="0,1000,10000,50000",
                        help="comma-separated existing log sizes (default 0,1000,10000,50000)")
    parser.add_argument("--reps", type=int, default=5, help="repetitions per cell (median)")
    parser.add_argument("--scratch", help="scratch directory (default: a new temporary one)")
    parser.add_argument("--json", help="also write the JSON result to this file")
    args = parser.parse_args()
    hs = [int(x) for x in args.h.split(",") if x.strip()]
    scratch = Path(args.scratch) if args.scratch else Path(tempfile.mkdtemp(prefix="banco-log-"))
    scratch.mkdir(parents=True, exist_ok=True)
    result = bench(hs, args.reps, scratch)
    result["scratch"] = str(scratch)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print()
    print(_table(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
