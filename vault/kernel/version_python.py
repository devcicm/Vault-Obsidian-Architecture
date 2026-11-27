"""Verificación única de versión mínima de Python soportada (DN-07, piso >= 3.10).

Hoja pura sin dependencias fuera de stdlib (`sys`, `typing`).
Se invoca en la entrada de la CLI (`vault/product_cli.py`) y en `wrap_main`
(`scripts/vault_errors.py`) para avisar de inmediato al usuario si ejecuta
una herramienta o intenta operar sobre una versión antigua de Python.
"""

from __future__ import annotations

import sys
from typing import Optional, Tuple

#: Versión mínima soportada por el estándar y declarada en `pyproject.toml`.
PYTHON_MINIMO: Tuple[int, int] = (3, 10)

#: URL oficial de descarga para actualizar Python.
URL_DESCARGA_PYTHON = "https://www.python.org/downloads/"


def comprobar_python_minimo(
    version_actual: Optional[Tuple[int, int]] = None,
) -> Optional[str]:
    """Devuelve un mensaje claro si Python es inferior a `PYTHON_MINIMO`, o `None` si cumple."""
    actual = (
        (int(version_actual[0]), int(version_actual[1]))
        if version_actual is not None
        else (sys.version_info[0], sys.version_info[1])
    )
    if actual < PYTHON_MINIMO:
        req = f"{PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]}"
        got = f"{actual[0]}.{actual[1]}"
        return (
            f"Tienes una versión vieja de Python ({got}); "
            f"Vault Obsidian Architecture requiere Python {req} o superior. "
            f"Necesitas actualizar Python ({URL_DESCARGA_PYTHON})."
        )
    return None
