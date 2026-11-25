"""Reglas de madurez XP / Augmented Coding (`xp_level: 1..4`) — hoja pura del núcleo (SPEC-03, SP-06).

Validación O(1) fail-closed sobre `00_System/reglas.json`: no toca disco ni
escanea carpetas (AP-66), así que puede ejecutarse dentro de `reglas_declaradas()`
sin coste ni riesgo de deadlock en `atomic_write_text`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

XP_LEVELS: Tuple[int, ...] = (1, 2, 3, 4)
XP_BUFFERS: Tuple[str, ...] = ("critical", "optional")

XP_LEVEL_NAMES: Dict[int, str] = {
    1: "Visibilidad (Sit Together + Stories con holgura)",
    2: "Contratos TDD (Rojo -> Verde -> Refactor obligatorio)",
    3: "Supervisión (Pair Programming incremental + revisión humana)",
    4: "Flujo continuo (Trunk-Based controlado)",
}

#: Claves requeridas en `xp_prerequisites` para autorizar Nivel 4 (Trunk-Based).
XP_PREREQUISITOS_NIVEL_4: Tuple[str, ...] = ("tdd_pass", "human_pair_review")


def validar_politica_xp(datos: Dict[str, Any]) -> Optional[str]:
    """Devuelve mensaje de error si `xp_level` o `xp_prerequisites` es inválido, o `None`.

    - Ausente o `None`: modo opt-in inactivo (retrocompatible).
    - Valor fuera de `{1, 2, 3, 4}` o booleano/texto: falla cerrado (SP-06).
    - Nivel 4 exige `xp_prerequisites: {"tdd_pass": true, "human_pair_review": true}`.
    """
    if "xp_level" not in datos or datos["xp_level"] is None:
        if "xp_prerequisites" in datos and not isinstance(datos["xp_prerequisites"], dict):
            return "SP-06: `xp_prerequisites` en reglas.json debe ser un objeto JSON."
        return None

    nivel = datos["xp_level"]
    if isinstance(nivel, bool) or not isinstance(nivel, int) or nivel not in XP_LEVELS:
        return (
            f"SP-06: `xp_level` inválido ({nivel!r}); debe ser un entero en {list(XP_LEVELS)}."
        )

    prereqs = datos.get("xp_prerequisites")
    if prereqs is not None and not isinstance(prereqs, dict):
        return "SP-06: `xp_prerequisites` debe ser un objeto JSON."

    if nivel == 4:
        prereqs = prereqs or {}
        faltantes = [k for k in XP_PREREQUISITOS_NIVEL_4 if prereqs.get(k) is not True]
        if faltantes:
            return (
                "SP-06: `xp_level: 4` (Trunk-Based) requiere prerequisitos verificados en "
                f"`xp_prerequisites` ({', '.join(f'{k}: true' for k in faltantes)}); "
                "no se puede saltar niveles 1-3."
            )
    return None
