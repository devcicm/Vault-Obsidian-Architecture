"""runner — ejecución aislada de fragmentos, en serie o en paralelo.

Cada tool corre en su propio subproceso. Es deliberado y cuesta ~50 ms de
arranque, a cambio de tres propiedades que in-process no da:

  - Aislamiento de estado. Las tools tienen estado a nivel de módulo
    (VAULT_ROOT cacheado, locks locales). Importarlas todas en un proceso y
    lanzarlas en hilos las haría compartir ese estado.
  - Timeout real. `vault_errors.wrap_main` corre main() en un hilo daemon: si
    la tool se cuelga, el hilo sobrevive. Matar un subproceso sí funciona.
  - Envelope garantizado. Se conserva el contrato JSON de cada tool tal cual,
    sin reinterpretarlo.

El paralelismo se aplica DENTRO de una ola del scheduler, donde por
construcción ninguna operación comparte recurso exclusivo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import REPO_ROOT, SCRIPTS_DIR
from .scheduler import Operation, Wave

DEFAULT_TIMEOUT = 120


@dataclass
class Result:
    op_id: str
    tool: str
    ok: bool
    exit_code: int
    duration_ms: int
    payload: Optional[Dict[str, Any]] = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    skipped: bool = False
    findings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.op_id,
            "tool": self.tool,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }
        if self.skipped:
            out["skipped"] = True
        if self.payload is not None:
            out["result"] = self.payload
        elif self.stdout:
            out["output"] = self.stdout[:4000]
        if self.error:
            out["error"] = self.error
        if self.stderr.strip():
            out["stderr"] = self.stderr[-2000:]
        if self.findings:
            out["findings"] = self.findings
        return out


def build_argv(op: Operation) -> List[str]:
    """Traduce args de la operación a la línea de comandos de la tool.

    Convención de argparse en este repo: todos los parámetros son largos
    (`--folder`). Los booleanos se pasan como flag sin valor; las listas se
    expanden en múltiples valores tras la misma flag.
    """
    frag = op.fragment
    script = SCRIPTS_DIR / (frag.script if frag else f"{op.tool}.py")
    argv = [sys.executable, str(script)]

    for key, value in op.args.items():
        flag = f"--{key.replace('_', '-')}"
        if value is True:
            argv.append(flag)
        elif value is False or value is None:
            continue
        elif isinstance(value, (list, tuple)):
            argv.append(flag)
            argv.extend(str(v) for v in value)
        elif isinstance(value, dict):
            argv.extend([flag, json.dumps(value, ensure_ascii=False)])
        else:
            argv.extend([flag, str(value)])
    return argv


def _parse_payload(stdout: str) -> Optional[Dict[str, Any]]:
    """Las tools emiten JSON. Se tolera ruido previo tomando la última línea útil."""
    text = stdout.strip()
    if not text:
        return None
    for candidate in (text, text.splitlines()[-1]):
        try:
            data = json.loads(candidate.lstrip("﻿"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IndexError):
            continue
    return None


def run_one(op: Operation, *, timeout: int = DEFAULT_TIMEOUT,
            dry_run: bool = False, cwd: Optional[Path] = None) -> Result:
    """Ejecuta una operación. Nunca lanza: los fallos vuelven como Result."""
    frag = op.fragment
    if frag is None:
        return Result(op.id, op.tool, False, 1, 0,
                      error=f"tool desconocida: '{op.tool}'")
    if frag.runtime == "node":
        return Result(op.id, op.tool, False, 1, 0,
                      error=f"'{op.tool}' es nativa del servidor MCP (Node)")
    if not frag.exists:
        return Result(op.id, op.tool, False, 1, 0,
                      error=f"script inexistente: {frag.script}")

    argv = build_argv(op)
    if dry_run:
        return Result(op.id, op.tool, True, 0, 0, skipped=True,
                      payload={"dry_run": True, "argv": argv[1:]})

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(cwd or REPO_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        elapsed = int((time.perf_counter() - start) * 1000)
        return Result(op.id, op.tool, False, 124, elapsed,
                      error=f"timeout tras {timeout}s — subproceso terminado")
    except OSError as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return Result(op.id, op.tool, False, 1, elapsed,
                      error=f"no se pudo lanzar: {exc}")

    elapsed = int((time.perf_counter() - start) * 1000)
    payload = _parse_payload(proc.stdout)
    # El exit code manda: una tool puede emitir {"ok": true} y salir 1.
    ok = proc.returncode == 0 and (payload is None or payload.get("ok") is not False)

    return Result(
        op_id=op.id,
        tool=op.tool,
        ok=ok,
        exit_code=proc.returncode,
        duration_ms=elapsed,
        payload=payload,
        stdout=proc.stdout if payload is None else "",
        stderr=proc.stderr,
    )


def run_wave(wave: Wave, *, timeout: int = DEFAULT_TIMEOUT,
             dry_run: bool = False, max_parallel: int = 4) -> List[Result]:
    """Ejecuta una ola. Sus operaciones no comparten recurso exclusivo."""
    if wave.isolated or len(wave.operations) == 1:
        return [run_one(op, timeout=timeout, dry_run=dry_run)
                for op in wave.operations]

    workers = min(max_parallel, len(wave.operations))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(run_one, op, timeout=timeout, dry_run=dry_run)
            for op in wave.operations
        ]
        return [f.result() for f in futures]
