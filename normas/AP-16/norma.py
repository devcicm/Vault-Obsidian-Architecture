"""AP-16 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-16",
    "distinguido_de": {
        "PAT-5": (
            "AP-16 es la falta del identificador de agente en una nota concreta. "
            "PAT-5 es el patrón que hace útil ese campo: el frontmatter como "
            "cadena de procedencia a lo largo de las ediciones. Un vault puede "
            "tener el campo en todas las notas y no encadenar nada."
        ),
        "AP-64": (
            "AP-16 registra quién **escribió** la nota; AP-64, quién "
            "**responde** de una decisión cerrada. Coinciden solo si la "
            "escribió una persona: un `agent: claude` con "
            "`responsable: claude` es el agente firmándose su propio porqué."
        ),
    },
    "name": "Sin identificador de agente en frontmatter",
    "type": "antipattern",
    "category": "frontmatter",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Nota sin campo agent: en el frontmatter. Sin este campo es imposible auditar "
        "qué agente creó o modificó la nota (PAT-5: frontmatter as provenance chain)."
    ),
    "signal": "vault_audit reporta notas sin campo agent.",
    "prevention": "vault_write agrega agent: automáticamente. Valores estándar: claude, system, human.",
    "tools_enforcing": ["vault_write", "vault_frontmatter_completar"],
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v20",
    "revisado_en": "2026-10-09",
}
