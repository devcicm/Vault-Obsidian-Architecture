#!/usr/bin/env python3
"""vault_merge — alias de `vault.autoria.merge` (ADR-0002, deuda #12).

El dueño vive en `vault/autoria/merge.py` desde 2026-10-10 (octava migración
del puente). Este nombre se conserva (no-derogación) como **alias en
`sys.modules`**, no como fachada que reexporta: `import vault_merge` devuelve el
módulo del dueño, así que un `monkeypatch.setattr(vault_merge, ...)` cambia lo que
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

if __name__ == "__main__":
    # Ejecutado como script, el `__main__` es el del dueño: un alias en
    # `sys.modules` no lo correría, porque el dueño se carga con su nombre.
    import runpy

    runpy.run_module("vault.autoria.merge", run_name="__main__", alter_sys=True)
else:
    import vault.autoria.merge as _dueno  # noqa: E402

    sys.modules[__name__] = _dueno
