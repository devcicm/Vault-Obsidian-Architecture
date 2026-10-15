"""AP-06 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-06",
    "distinguido_de": {
        "AP-11": (
            "AP-06 es la plantilla que nadie instanció: el fichero es un template "
            "y su función es serlo. AP-11 es la nota real con frontmatter válido "
            "y cuerpo vacío, que se presenta como contenido. El discriminador es "
            "si el fichero se declara plantilla."
        ),
    },
    "name": "Templates sin instancias reales",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault "
        "pero nunca se han instanciado con datos reales."
    ),
    "signal": "Notas con status:template que no tienen notas derivadas con wiki-link hacia ellas.",
    "prevention": "Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}
