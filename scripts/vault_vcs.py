#!/usr/bin/env python3
"""vault_vcs — fachada de `vault.kernel.vcs` (capa de git del vault).

El dueño vive en `vault/kernel/vcs.py` (v41.26). Este nombre existe por la
misma razón que `vault_ledger` y `vault_subproceso`: el grafo de imports del
repo (y el gate del núcleo, AP-59) miden los módulos por su nombre `vault_*`,
y un módulo del núcleo sin fachada no tiene consumidor medible — `vault_kernel`
lo reporta como `kernel_sin_consumidores`, que es exactamente lo que pasó al
estrenarlo.

No es una copia: `import vault_vcs` devuelve el módulo del dueño, así que un
`monkeypatch` sobre uno cambia lo que ve el otro. En el checkout añade la raíz
del repo al path para encontrar `vault/`; instalado (en `_impl`) ya es
importable.
"""

import sys
from pathlib import Path

_repo_root = next(
    (p for p in Path(__file__).resolve().parents if (p / "vault").is_dir()),
    None,
)
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import vault.kernel.vcs as _dueno  # noqa: E402

sys.modules[__name__] = _dueno
