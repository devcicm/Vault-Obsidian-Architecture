#!/usr/bin/env python3
"""Ejecutor de gates de producto: clean_install + memory_e2e.

Ejecuta los gates en orden, cada uno en su propio directorio temporal bajo
vault-sandbox/00_System/product-gates/. Los resultados completos (stdout, stderr, código
de salida) se persisten en el sandbox.

Cobertura:
  clean_install_gate  — wheel limpio, instalación con deps, init, doctor, status,
                       idempotencia, portabilidad del runtime
  memory_e2e_gate    — escritura y recuperación de conocimiento entre procesos
                       separados, verificación de que no hay fuga de sys.path ni
                       de árbol fuente después de instalar
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# CN-02: los resultados son informes del vault y viven en `00_System/`, como
# `quality-index.json`. En la raíz, `product-gates/` era una carpeta que el
# vault no declara y el audit del sandbox salía con un CN-02 alto causado por
# este arnés, no por ninguna nota.
SANDBOX = REPO_ROOT / "vault-sandbox" / "00_System" / "product-gates"


def _run_gate(name: str, script: Path) -> tuple[int, str, str]:
    print(f"\n{'='*60}\n=== {name}\n{'='*60}")
    gate_dir = SANDBOX / name
    gate_dir.mkdir(parents=True, exist_ok=True)
    result_file = gate_dir / f"{name}-result.json"

    env = os.environ.copy()

    try:
        proc = subprocess.run(
            [sys.executable, str(script.resolve())],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=600,
        )
        code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        code = -1
        stdout = getattr(exc, "stdout", "") or ""
        stderr = getattr(exc, "stderr", "") or ""
        stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
    except Exception as exc:
        code = -2
        stdout = ""
        stderr = f"runner error: {type(exc).__name__}: {exc}"

    output = {
        "gate": name,
        "exit_code": code,
        "stdout": stdout,
        "stderr": stderr,
        "command": [sys.executable, str(script.resolve())],
        "sandbox_dir": str(gate_dir),
        "timestamp": time.time(),
    }

    result_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"exit={code}")
    if stdout:
        print("STDOUT (last 40 lines):")
        for line in stdout.splitlines()[-40:]:
            print(f"  {line}")
    if stderr:
        print("STDERR (last 20 lines):")
        for line in stderr.splitlines()[-20:]:
            print(f"  {line}")

    return code, stdout, stderr


def main() -> int:
    gates = [
        ("clean_install", REPO_ROOT / "tests" / "clean_install_gate.py"),
        ("memory_e2e", REPO_ROOT / "tests" / "memory_recovery_e2e_gate.py"),
    ]

    results = []
    for name, script in gates:
        code, stdout, stderr = _run_gate(name, script)
        results.append({"gate": name, "code": code})

    print(f"\n{'='*60}\n=== Summary\n{'='*60}")
    for r in results:
        status = "PASS" if r["code"] == 0 else "FAIL"
        print(f"  {r['gate']}: {status} (exit={r['code']})")

    all_pass = all(r["code"] == 0 for r in results)
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
