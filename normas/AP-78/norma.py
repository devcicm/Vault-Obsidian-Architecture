"""AP-78 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-78",
    "name": "Decisión de IA de impacto alto sin evaluación por afectado",
    "type": "antipattern",
    "category": "process",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "ISO/IEC 42005 no se queda en a quién afecta una decisión de IA: la "
        "evaluación completa dice, por cada afectado, cuán probable es el "
        "daño, cuán grave y cómo se mitiga. AP-65 vigila lo primero; una "
        "decisión de impacto alto que nombra a sus afectados y nada más pasa "
        "AP-65 con la evaluación a medias. Desde esta norma "
        "`vault_ai_decision --assessment` registra probabilidad y severidad en "
        "las escalas 1-5 de `vault_risk_save` y la mitigación de cada "
        "afectado, y declara `evaluacion_por_afectado` (`completa` o "
        "`parcial`)."
    ),
    "signal": (
        "Nota de `16_AI_Governance/` con `impact_level` en los niveles que "
        "exigen evaluación (`niveles_de_impacto_exigidos` sobre `severidad`: "
        "`critical`, `high`), que no sea plantilla, con `impact_assessment: "
        "completa` y cuyo `evaluacion_por_afectado` no sea `completa` —también "
        "si no lo declara—. La que ni siquiera dice a quién afecta es de "
        "AP-65 y no se cuenta dos veces."
    ),
    "prevention": (
        "Al registrar una decisión de impacto alto, pasar `--assessment` con "
        "una entrada por afectado: `vault_ai_decision ... --impact_level high "
        "--assessment '[{\"affected\": \"usuarios finales\", \"likelihood\": 3, "
        "\"impact\": 4, \"mitigation\": \"refresco silencioso del token\"}]'`. "
        "Una entrada mal formada se rechaza sin escribir nada "
        "(`INVALID_LIKELIHOOD`, `INVALID_IMPACT`, `INVALID_VALUE`); un "
        "afectado sin entrada deja la evaluación `parcial` y el envelope lo "
        "nombra en `hint`. `vault_audit` publica la lista de trabajo en "
        "`aiDecisionsWithoutPartyAssessment`.\n\n"
        "Límites declarados: la norma sabe que cada afectado tiene su "
        "probabilidad, su severidad y su mitigación, no que estén bien "
        "estimadas; la evaluación del sistema de IA en su conjunto, a lo "
        "largo de su ciclo de vida, es de la organización."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "distinguido_de": {
        "AP-65": (
            "AP-65 pregunta si la decisión de impacto alto dice a quién afecta; "
            "AP-78, si por cada afectado dice cuán probable y grave es el daño "
            "y cómo se mitiga. Una decisión pasa AP-65 con `--affected` y sigue "
            "en AP-78 hasta que cada afectado tiene su evaluación."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-18",
}
