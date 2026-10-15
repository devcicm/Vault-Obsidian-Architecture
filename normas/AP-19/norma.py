"""AP-19 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-19",
    "distinguido_de": {
        "AP-18": (
            "AP-18 duplica contenido en dos carpetas. AP-19 duplica el índice: "
            "hay un índice en la sombra que compite con el canónico. El "
            "discriminador es si lo duplicado es material o navegación."
        ),
    },
    "name": "Shadow indexing",
    "type": "antipattern",
    "category": "structure",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Índices de sección creados manualmente, duplicando lo que vault_section_index genera "
        "automáticamente. Los índices manuales rotan en AP-02 con el tiempo."
    ),
    "signal": "Múltiples index.md o README.md en una sección que no fueron generados por vault_section_index.",
    "prevention": "vault_section_index es la única herramienta para índices. No editar index.md manualmente.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v25",
    "revisado_en": "2026-10-09",
}
