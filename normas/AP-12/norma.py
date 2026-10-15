"""AP-12 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-12",
    "distinguido_de": {
        "AP-46": (
            "AP-12 es el síntoma medido en las notas: dos notas del mismo tipo "
            "con frontmatter distinto. AP-46 es la causa medida en el código: no "
            "hay escritor único de frontmatter. Se separan porque el vault puede "
            "quedar coherente a mano con la causa intacta."
        ),
    },
    "name": "Frontmatter inconsistente entre notas del mismo tipo",
    "type": "antipattern",
    "category": "frontmatter",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Notas del mismo tipo con campos faltantes, tipos mezclados "
        "(timestamp con/sin comillas, migratedFrom relativo vs absoluto). "
        "Rompe vault_list, búsquedas y deduplicación."
    ),
    "signal": "vault_validate reporta campos faltantes. vault_audit detecta inconsistencias de tipo.",
    "prevention": "vault_write como único punto de creación; nunca editar frontmatter manualmente.",
    "tools_enforcing": ["vault_write", "vault_frontmatter_completar"],
    # `vault_audit` no mide AP-12: mide los campos uno a uno (AP-16, AP-26,
    # AP-27, AP-29, AP-30), cada uno con su penalización. Quien comprueba el
    # bloque completo es `vault_validate.validate_frontmatter`.
    "tools_detecting": ["vault_validate"],
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}
