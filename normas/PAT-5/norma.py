"""PAT-5 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "PAT-5",
    "distinguido_de": {
        "AP-16": (
            "AP-16 es la falta del identificador de agente en una nota concreta. "
            "PAT-5 es el patrón que hace útil ese campo: el frontmatter como "
            "cadena de procedencia a lo largo de las ediciones. Un vault puede "
            "tener el campo en todas las notas y no encadenar nada."
        ),
    },
    "name": "Frontmatter as provenance chain",
    "type": "pattern",
    "category": "frontmatter",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Los campos id + createdAt + updatedAt + agent + migratedFrom (si aplica) "
        "forman una cadena de custodia completa. Sin esta cadena es imposible auditar "
        "de dónde vino un dato o qué agente lo introdujo."
    ),
    "signal": "vault_audit reporta 0 notas sin campo agent.",
    "prevention": "N/A — vault_write genera estos campos automáticamente.",
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_write", "vault_audit"],
    "introduced_version": "v25",
    "revisado_en": "2026-10-09",
}
