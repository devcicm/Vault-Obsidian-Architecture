#!/usr/bin/env python3
"""Vault Regex — re-export desde vault.kernel.regex (scripts y _impl).

En el checkout añade la raíz del repo al path para encontrar vault/;
instalado (en _impl) vault ya es importable. Reexporta vault.kernel.regex.
"""

import sys
from pathlib import Path

_repo_root = next(
    (p for p in Path(__file__).resolve().parents if (p / "vault").is_dir()),
    None,
)
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from vault.kernel.regex import *
from vault.kernel.regex import __all__
