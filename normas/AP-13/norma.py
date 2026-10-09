"""AP-13 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-13",
    "distinguido_de": {
        "AP-53": (
            "AP-13 mide el timestamp del frontmatter contra su propio formato: "
            "inválido o incompleto. AP-53 mide la afirmación histórica contra "
            "git: la fecha es valida y no coincide con el commit. El "
            "discriminador es si hay una fuente externa contra la que contrastar."
        ),
    },
    "name": "Timestamps inválidos o incompletos en frontmatter",
    "type": "antipattern",
    "category": "frontmatter",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Timestamps solo con fecha (2026-05-07), con '...' literal, sin zona horaria "
        "o en formato no ISO 8601. vault_diff y vault_timeline no pueden ordenar versiones."
    ),
    "signal": "vault_audit detecta createdAt/updatedAt que no coinciden con patrón ISO 8601.",
    "prevention": "vault_write genera timestamps con datetime.now(timezone.utc).isoformat() automáticamente.",
    "tools_enforcing": ["vault_write"],
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v19",
}
