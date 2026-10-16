"""AP-29 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-29",
    "distinguido_de": {
        "AP-30": (
            "Las dos son campos ausentes. AP-29 es `status`, el estado del ciclo "
            "de vida, que cambia con el tiempo. AP-30 es la clasificación CIA, "
            "que describe la sensibilidad del contenido y no cambia por avanzar "
            "el trabajo. El discriminador es si el valor es temporal o "
            "intrínseco."
        ),
        "CN-03": (
            "CN-03 exige que el valor de `status` esté en el vocabulario "
            "canónico; AP-29 exige que el campo exista. El discriminador es "
            "presencia frente a valor: una nota sin `status` es AP-29 y no puede "
            "ser CN-03."
        ),
    },
    "name": "Missing status field — nota sin estado de ciclo de vida",
    "type": "antipattern",
    "category": "metadata-completeness",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Nota sin campo `status`. Sin estado no se puede distinguir lo vigente de "
        "lo obsoleto, y la nota escapa al vocabulario controlado de CN-03: es la "
        "vía por la que contenido derogado sigue leyéndose como vigente."
    ),
    "signal": "vault_audit la cuenta en missing_status y penaliza -1 por nota (tope -10).",
    "prevention": "Declarar --status dentro de STATUS_VOCAB (12 valores).",
    "tools_enforcing": ["vault_frontmatter_completar"],
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
