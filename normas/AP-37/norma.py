"""AP-37 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-37",
    "name": "No-op silencioso — ok: true sin indicador de trabajo",
    "type": "antipattern",
    "category": "observability",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Una tool con side effects declarados devuelve ok: true sin exponer ningún "
        "campo que distinga 'hice N cosas' de 'no hice nada'. `ok: true` a secas es "
        "una afirmación no falsable: ni un test ni un agente pueden detectar que la "
        "operación fue vacía. Toda tool que modifica estado debe declarar un "
        "indicador de trabajo en declared_returns (changed, applied, count, "
        "migrations_applied, fixes_applied, skipped, no_op…) y devolverlo siempre, "
        "también cuando vale 0."
    ),
    "signal": (
        "declared_returns sin ningún campo de conteo o cambio en una tool con "
        "side_effects; tests que solo afirman result['ok'] sobre operaciones "
        "mutantes."
    ),
    "prevention": (
        "Declarar el indicador en tool-spec.json y devolverlo desde la tool. "
        "vault_noop_audit --check compara el catálogo contra una baseline "
        "congelada: la deuda histórica no bloquea, pero NO puede crecer."
    ),
    "tools_enforcing": ["vault_noop_audit"],
    "tools_detecting": ["vault_noop_audit"],
    "distinguido_de": {
        "AP-60": (
            "AP-37 es el `ok: true` que ninguna evidencia podría "
            "contradecir; AP-60 es la medida que sí se puede refutar pero "
            "solo mira a quien se declaró. Un guard AP-60 publica un total "
            "verdadero de un universo equivocado — comprobable, y por eso "
            "no es AP-37."
        ),
        "AP-66": (
            "AP-37 pregunta si una tool dice cuánto trabajo hizo; AP-66, "
            "si su coste crece con ese trabajo o con otra cosa. Una tool "
            "puede declarar `written` exacto y tardar con la historia del repo."
        ),
    },
    "introduced_version": "v39",
    "revisado_en": "2026-10-09",
}
