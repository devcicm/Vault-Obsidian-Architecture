"""vault.meta_toolkit.estandar.corredor_suite — lanzador de pytest consciente del hardware.

Resuelve dos problemas reales de la suite (~7.980 tests):
1. En Windows con 12-16 hilos, `-n auto` lanza 16 workers × subprocesos hijos y
   agota el Desktop Heap (`0xC0000142`), mientras que `-n 4` con `--dist=load`
   deja colas ociosas al final y tarda 15-25 min. Usar `min(8, max(4, cpus // 2))`
   workers con `--dist=worksteal` + orden LPT (`conftest.py`) + `PYTHONDONTWRITEBYTECODE=1`
   maximiza uso real sin reventar handles de Windows.
2. En hardware modesto (Pentium / CPU de 2-4 hilos), abrir demasiados workers ahoga
   CPU y disco. El plan ajusta `workers = 2` (en 2 hilos) o `3` (en 4 hilos),
   informa la estimación real basada en `tests/duraciones-por-modulo.json` (sin
   promesas falsas contra la ley de Amdahl) y expone el carril `--modo rapida`
   (`-m "not slow"`) para iterar en pocos minutos.

Uso:
    python -m vault.meta_toolkit.estandar.corredor_suite --plan
    python -m vault.meta_toolkit.estandar.corredor_suite --modo rapida
    python -m vault.meta_toolkit.estandar.corredor_suite --modo completa
    python -m vault.meta_toolkit.estandar.corredor_suite --modo bloque --bloque escritura
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault.kernel import rutas
from vault.kernel.errores import construir_error
from vault.meta_toolkit.estandar import inventario_tests, perfil_suite


def plan_hardware(
    cpus: Optional[int] = None,
    sistema: Optional[str] = None,
    modo: str = "completa",
    bloque: Optional[str] = None,
    workers_forzados: Optional[int] = None,
) -> Dict[str, Any]:
    """Calcula workers seguros, estrategia xdist y estimación realista para el hardware."""
    hilos = max(1, int(cpus if cpus is not None else (os.cpu_count() or 2)))
    so = (sistema or platform.system()).lower()
    es_windows = so.startswith("win")

    if workers_forzados is not None:
        workers = max(1, int(workers_forzados))
        motivo = f"forzado por --workers={workers}"
    elif hilos <= 2:
        workers = 2 if hilos == 2 else 1
        motivo = "hardware modesto (<=2 hilos): acota workers para evitar thrashing de CPU/disco"
    elif hilos <= 4:
        workers = 3 if es_windows else 4
        motivo = "hardware 3-4 hilos: deja 1 hilo libre al SO/IO en Windows"
    elif es_windows:
        # Windows agota Desktop Heap (0xC0000142) con >=12 workers lanzando subprocesos
        workers = min(8, max(4, hilos // 2))
        motivo = "Windows >=5 hilos: techo seguro de 8 workers para evitar 0xC0000142 con subprocesos"
    else:
        workers = min(12, max(4, hilos - 2))
        motivo = "Linux/Unix: deja 2 hilos libres y usa worksteal + LPT"

    pesos = perfil_suite.pesos()
    lentos = perfil_suite.lentos(pesos)
    trabajo_total_s = sum(pesos.values()) if pesos else 0.0
    trabajo_lentos_s = sum(lentos.values()) if lentos else 0.0

    if modo == "rapida":
        trabajo_objetivo_s = max(0.0, trabajo_total_s - trabajo_lentos_s)
    else:
        trabajo_objetivo_s = trabajo_total_s

    # Factor conservador de overhead de subprocesos (~1.18 en Windows, ~1.08 en Linux)
    factor_so = 1.18 if es_windows else 1.08
    estimado_min = round((trabajo_objetivo_s / max(1, workers)) * factor_so / 60.0, 1) if trabajo_objetivo_s else None

    cmd: List[str] = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "-n",
        str(workers),
        "--dist=worksteal",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    if modo == "rapida":
        cmd.extend(["-m", "not slow"])
    elif modo == "bloque":
        if not bloque or bloque not in inventario_tests.BLOQUES:
            raise ValueError(
                f"--bloque debe ser uno de {sorted(inventario_tests.BLOQUES)}, recibido: {bloque!r}"
            )
        cmd.extend(["-m", f"{bloque} and not slow"])
    elif modo != "completa":
        raise ValueError(f"--modo invalido: {modo!r}. Usa 'rapida', 'completa' o 'bloque'.")

    nota_hardware = ""
    if hilos <= 4 and modo == "completa":
        nota_hardware = (
            "Hardware de 2-4 hilos: por ley de Amdahl la suite completa supera 10 min; "
            "usa `--modo rapida` (sin slow) o `--modo bloque` durante el desarrollo."
        )

    return {
        "ok": True,
        "cpus": hilos,
        "sistema": so,
        "modo": modo,
        "bloque": bloque,
        "workers": workers,
        "dist": "worksteal",
        "lpt_enabled": True,
        "motivo_workers": motivo,
        "trabajo_perfilado_s": round(trabajo_objetivo_s, 1),
        "estimado_min": estimado_min,
        "nota_hardware": nota_hardware,
        "command": cmd,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Corredor de pytest consciente del hardware (LPT + worksteal + techo seguro Windows).",
        allow_abbrev=False,
    )
    ap.add_argument(
        "--modo",
        choices=("completa", "rapida", "bloque"),
        default="completa",
        help="completa (carril merge), rapida (not slow) o bloque (un dominio sin slow)",
    )
    ap.add_argument("--bloque", help="Nombre del bloque cuando --modo=bloque")
    ap.add_argument("--workers", type=int, default=None, help="Forzar numero de workers")
    ap.add_argument("--plan", action="store_true", help="Solo mostrar el plan JSON sin ejecutar")
    args = ap.parse_args()

    try:
        plan = plan_hardware(modo=args.modo, bloque=args.bloque, workers_forzados=args.workers)
    except ValueError as exc:
        err = construir_error("corredor_suite", "INVALID_INPUT", message=str(exc), exception=exc)
        print(json.dumps(err, ensure_ascii=False))
        return 2

    if args.plan:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(plan["command"], cwd=str(rutas.raiz_repo()), env=env)
    return int(proc.returncode)


if __name__ == "__main__":
    sys.exit(main())
