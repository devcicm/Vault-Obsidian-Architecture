#!/usr/bin/env python3
"""vault_raiz — alias de `vault.kernel.raiz` (ADR-0002, deuda #12).

El dueño vive en `vault/kernel/raiz.py` desde 2026-10-16 (lote A de la quinta tanda,
raíces del kernel que se anclaban en su `__file__`). Este nombre se conserva
(no-derogación) como **alias en `sys.modules`**, no como fachada que reexporta:
`import vault_raiz` devuelve el módulo del dueño, así que un
`monkeypatch.setattr(vault_raiz, ...)` cambia lo que el dueño ve, y no hay dos copias
de nada. En el checkout añade la raíz del repo al path para encontrar `vault/`;
instalado (en `_impl`) ya es importable.
"""

import sys
from pathlib import Path

_repo_root = next(
    (p for p in Path(__file__).resolve().parents if (p / "vault").is_dir()),
    None,
)
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import vault.kernel.raiz as _dueno  # noqa: E402

sys.modules[__name__] = _dueno
