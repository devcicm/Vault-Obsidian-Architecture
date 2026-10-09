#!/usr/bin/env python3
"""vault_subproceso — fachada de `vault.kernel.subproceso` (ADR-0002, deuda #12).

El dueño vive en `vault/kernel/subproceso.py` desde 2026-10-09: fue la primera
migración del puente. Este nombre se conserva porque lo importan tools, guards y
tests (no-derogación), y reexporta los mismos objetos, no una copia. En el
checkout añade la raíz del repo al path para encontrar `vault/`; instalado (en
`_impl`) `vault` ya es importable. Es la forma de `vault_regex`.
"""

import sys
from pathlib import Path

_repo_root = next(
    (p for p in Path(__file__).resolve().parents if (p / "vault").is_dir()),
    None,
)
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from vault.kernel.subproceso import CODIFICACION, ERRORES, ejecutar, sitios_sin_codificacion  # noqa: E402

__all__ = ["CODIFICACION", "ERRORES", "ejecutar", "sitios_sin_codificacion"]
