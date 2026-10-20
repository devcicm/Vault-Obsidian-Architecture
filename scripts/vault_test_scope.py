#!/usr/bin/env python3
"""vault_test_scope — alias de `vault.meta_toolkit.test_scope` (ADR-0002, deuda #12).

El dueño vive en `vault/meta_toolkit/test_scope.py` desde v41.12. Este nombre se
conserva (no-derogación) como **alias en `sys.modules`**, no como fachada que
reexporta: `import vault_test_scope` devuelve el módulo del dueño, y un
`monkeypatch.setattr(vault_test_scope, ...)` cambia lo que el dueño ve. En el
checkout añade la raíz del repo al path para encontrar `vault/`; instalado (en
`_impl`) ya es importable.
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

    runpy.run_module("vault.meta_toolkit.test_scope", run_name="__main__", alter_sys=True)
else:
    import vault.meta_toolkit.test_scope as _dueno  # noqa: E402

    sys.modules[__name__] = _dueno
