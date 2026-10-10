#!/usr/bin/env python3
"""vault_errors_trace — alias de `vault.kernel.errors_trace` (ADR-0002, deuda #12).

El dueño vive en `vault/kernel/errors_trace.py` desde 2026-10-10 (lote H de la migración
del puente). Este nombre se conserva (no-derogación) como **alias en
`sys.modules`**, no como fachada que reexporta: `import vault_errors_trace` devuelve el
módulo del dueño, así que un `monkeypatch.setattr(vault_errors_trace, ...)` cambia lo que
el dueño ve, y no hay dos copias de nada. En el checkout añade la raíz del
repo al path para encontrar `vault/`; instalado (en `_impl`) ya es importable.
"""

import sys
from pathlib import Path

_repo_root = next(
    (p for p in Path(__file__).resolve().parents if (p / "vault").is_dir()),
    None,
)
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import vault.kernel.errors_trace as _dueno  # noqa: E402

sys.modules[__name__] = _dueno
