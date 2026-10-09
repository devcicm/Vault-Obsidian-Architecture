"""AP-65 — la entrada del catálogo, en su paquete (deuda #10, piloto).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG`; el porqué de cada cara está en
`porque.md`.
"""

NORMA = {
    "code": "AP-65",
    "name": "Decisión de IA de impacto alto sin evaluación de impacto",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "ISO/IEC 42001 pide registrar qué decidió un sistema de IA y por "
        "qué; ISO/IEC 42005 añade a quién afecta. `vault_ai_decision` "
        "registraba lo primero y no tenía dónde escribir lo segundo: una "
        "decisión `critical` quedaba con su porqué y sin el coste que "
        "reparte. Desde v41.3 la tool acepta `--affected` y declara "
        "`impact_assessment` (`completa`, `pendiente` o `no_exigida`).\n\n"
        "El criterio tiene dueño en `vault.kernel.contenido."
        "falta_de_evaluacion_de_impacto` —con su ámbito y los niveles que "
        "exigen evaluación, `niveles_de_impacto_exigidos` sobre la escala "
        "`severidad` de `vault_vocabulario`— y lo leen la tool al escribir, "
        "el scan y la auditoría."
    ),
    "signal": (
        "Nota de `16_AI_Governance/` con `impact_level` en los dos niveles "
        "más altos de la escala (`critical`, `high`), que no sea plantilla, "
        "y cuyo `impact_assessment` no sea `completa` —también si no lo "
        "declara—."
    ),
    "prevention": (
        "Al registrar una decisión de impacto alto, pasar `--affected` con "
        "a quién afecta y cómo: `vault_ai_decision ... --impact_level high "
        "--affected '[\"usuarios finales - pierden la sesión al desplegar\"]'`. "
        "Sin él la nota se escribe igual —un registro incompleto vale más "
        "que ninguno— con `impact_assessment: pendiente`, y el envelope lo "
        "dice en `hint`.\n\n"
        "Límites declarados: la norma sabe que la nota nombra afectados, no "
        "que la evaluación sea buena; la evaluación completa de 42005 "
        "(probabilidad, severidad por afectado, mitigación) no se mide. "
        "Contrastada en solo lectura contra los vaults ajenos y las copias "
        "de los trece consumidores (regla 7, 2026-10-08): ninguno tiene "
        "decisiones de IA con `impact_level`, así que el contraste no "
        "ejerció el detector sobre material real."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "distinguido_de": {
        "AP-64": (
            "AP-64 pregunta quién responde de un ADR cerrado; AP-65, a quién "
            "afecta una decisión de IA de impacto alto. Una decisión de IA "
            "aprobada por una persona (`human_approved`) puede seguir sin "
            "decir a quién le cuesta."
        ),
    },
    "introduced_version": "v41.3",
}
