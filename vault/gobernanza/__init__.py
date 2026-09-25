"""Contexto **Gobernanza**: la norma y su cumplimiento.

Lenguaje ubicuo: norma, guard, enforcement, severidad, violación, puntuación de
calidad, deriva. Es dueño del registro de normas, del índice de calidad, de la
instantánea de sesión y de `02_Observability/vulnerabilities/`.

Es el contexto con más acoplamiento entrante del estándar: veintisiete módulos
de siete contextos importan `vault_norms`. Eso no se salda aquí —son los
consumidores quienes tienen que pasar por el puerto— y sigue declarado como
deuda en la baseline de `vault_arch`.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from .repositorio import RepositorioGobernanza
from .base import (
    GobernanzaBase,
    ValidationResult,
    AuditResult,
    ToolNature,
    ToolFragment,
    ToolsCatalog,
    NormCatalog,
)
from .cli_gobernanza import GobernanzaCLI
from .mcp_gobernanza import GobernanzaMCP

__all__ = [
    "RepositorioGobernanza",
    "GobernanzaBase",
    "ValidationResult",
    "AuditResult",
    "ToolNature",
    "ToolFragment",
    "ToolsCatalog",
    "NormCatalog",
    "GobernanzaCLI",
    "GobernanzaMCP",
]
