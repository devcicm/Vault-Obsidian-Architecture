"""AP-07 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-07",
    "distinguido_de": {
        "AP-10": (
            "Las dos son documentos de proceso incompletos. AP-07 es el ADR al "
            "que le faltan secciones obligatorias —contexto, decisión, "
            "consecuencias—. AP-10 es la migración sin plan de rollback: el "
            "documento puede estar completo en todo lo demás. El discriminador es "
            "que AP-10 nombra una sección concreta cuya ausencia es "
            "operativamente peligrosa."
        ),
        "AP-64": (
            "Las dos miran el mismo ADR. AP-07 pregunta si el porqué está "
            "escrito —contexto, decisión, consecuencias—; AP-64, si alguien "
            "responde de él. Un ADR puede tener las tres secciones y que "
            "nadie lo firme, o estar firmado y sin contexto."
        ),
    },
    "name": "ADRs incompletos",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "ADRs (Architecture Decision Records) sin secciones Contexto, Decisión "
        "y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría. "
        "Opciones evaluadas se recomienda y no se exige desde v41.3: medido contra "
        "un vault ajeno (regla 7), ocho de diez ADR reales registran el porqué sin "
        "esa sección. El criterio tiene dueño en `vault.kernel.contenido` "
        "(`es_adr`, `secciones_adr_faltantes`) y lo leen el scan y la auditoría."
    ),
    "signal": (
        "Nota de 03_Decisions/ —sin `type` o con `type: adr|decision`, que no sea "
        "índice ni primer— sin un encabezado que nombre Contexto, Decisión y "
        "Consecuencias (castellano o inglés, sin importar tildes)."
    ),
    "prevention": (
        "Escribir el ADR desde `vault.kernel.contenido.plantilla_adr()` "
        "(Contexto, Opciones, Decisión, Consecuencias), la misma que propone "
        "la guía de vault_audit, con el frontmatter de `meta_adr()` "
        "(`type: adr`, `status: draft`)."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v19",
}
