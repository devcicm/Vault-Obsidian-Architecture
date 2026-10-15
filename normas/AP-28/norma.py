"""AP-28 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-28",
    "name": "Missing frontmatter — nota sin bloque YAML",
    "type": "antipattern",
    "category": "metadata-completeness",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Nota sin bloque de frontmatter. Es el caso degenerado de AP-26/27/29/30 "
        "a la vez: sin frontmatter no hay id, ni agent, ni status, ni CIA, así que "
        "la nota queda fuera de toda métrica de calidad y de la cadena de "
        "trazabilidad (PAT-5)."
    ),
    "signal": "vault_audit la cuenta en missing_frontmatter y penaliza -3 por nota (tope -20).",
    "prevention": (
        "No editar .md a mano (SP-04). Escribir siempre por tool: "
        "atomic_write_text garantiza el bloque."
    ),
    "tools_enforcing": ["vault_frontmatter_completar"],
    "tools_detecting": ["vault_audit", "vault_validate"],
    "distinguido_de": {
        "AP-56": (
            "AP-28 es ausencia: no hay bloque `---` que leer. AP-56 es presencia "
            "ilegible: el bloque está, el humano lo ve al abrir la nota, y el "
            "consumidor no lo lee porque no parsea. Se confunden porque ambas "
            "acaban en 'esta nota no tiene metadatos', pero la reparación es "
            "opuesta: AP-28 pide escribir el frontmatter, AP-56 pide arreglar el "
            "que ya está — y escribir uno nuevo encima perdería lo escrito."
        )
    },
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
