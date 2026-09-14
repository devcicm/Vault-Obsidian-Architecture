#!/usr/bin/env python3
"""Adaptador histórico del contrato estable de errores.

La autoridad vive en ``vault.kernel.errores`` para que un producto instalado
no necesite importar ``scripts/``. Se reexportan los nombres públicos para
preservar los consumidores históricos.
"""

from vault.kernel.errores import ERROR_CATALOG, construir_error, get_error

__all__ = ["ERROR_CATALOG", "construir_error", "get_error"]
