"""Safety para herramientas de consulta — reexport sin derogación de `vault.kernel.safety`.

superseded_by: `vault.kernel.safety` (Fase H, 2026-11-25). Se conserva este
módulo para que `cli/safety.py` y todos los llamadores existentes sigan
funcionando sin romper contratos ni introducir cruces `autoria -> consulta`.
"""

from vault.kernel.safety import (  # noqa: F401
    Finding,
    SENSITIVITY_ORDER,
    _INJECTION_PATTERNS,
    _INVISIBLE,
    _RE_SAFETY_1,
    _TAG_BLOCK,
    _prose_only_lines,
    excede_sensibilidad,
    scan_content,
    scan_poison,
)
