"""Permite `python -m cli`.

Este es el punto de entrada, y por eso es aquí donde `scripts/` entra en
`sys.path`: `registry`, `runner` y `resolver` no pueden hacerlo
(`test_puntos_distribuibles_no_insertan_scripts_en_sys_path`). Desde
f1132aa, que se lo quitó a `registry` sin dárselo a nadie, `python -m cli`
caía al arrancar con `No module named 'vault_vocabulario'`; la suite no lo
veía porque cada test pone `scripts/` en `sys.path` antes de importar `cli`.
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from .vault_cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
