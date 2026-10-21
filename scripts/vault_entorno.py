#!/usr/bin/env python3
"""vault_entorno — alias de `vault.kernel.entorno` (ADR-0002, deuda #12).

El dueño vive en `vault/kernel/entorno.py` desde 2026-10-09 (sexta migración
del puente). Este nombre se conserva (no-derogación) como **alias en
`sys.modules`**, no como fachada que reexporta: `import vault_entorno` devuelve el
módulo del dueño, así que un `monkeypatch.setattr(vault_entorno, ...)` cambia lo que
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

import vault.kernel.entorno as _dueno  # noqa: E402

sys.modules[__name__] = _dueno


if __name__ == "__main__":
    # O8 — el comando que publica presupuesto y help de cada variable (AP-05:
    # el registro es la fuente; esto es presentación). `--filtro` acota por
    # nombre o propósito; `--json` para consumir. El parser vive en el DUEÑO
    # (como el resto de alias, ADR-0002), y la puerta de documentación lee
    # los flags de ahí.
    import vault.kernel.entorno as _dueno_cli

    sys.exit(_dueno_cli.main())
