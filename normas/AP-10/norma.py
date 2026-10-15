"""AP-10 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-10",
    "distinguido_de": {
        "AP-07": (
            "Las dos son documentos de proceso incompletos. AP-07 es el ADR al "
            "que le faltan secciones obligatorias —contexto, decisión, "
            "consecuencias—. AP-10 es la migración sin plan de rollback: el "
            "documento puede estar completo en todo lo demás. El discriminador es "
            "que AP-10 nombra una sección concreta cuya ausencia es "
            "operativamente peligrosa."
        ),
    },
    "name": "Migración sin plan de rollback",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Ejecutar vault_migrate_docs sin tener vault_migrate_rollback disponible "
        "o sin snapshot previo. Si la migración introduce errores, no hay manera de revertir."
    ),
    "signal": "vault_migrate_docs ejecutado sin llamar vault_drift_detect --mode snapshot primero.",
    "prevention": "PAT-4 (phased audit): siempre snapshot → migrate → verify → rollback si falla.",
    "tools_enforcing": [],
    # `vault_migrate_rollback` **es** el rollback: tenerlo no detecta que una
    # migración se hizo sin él. Quien lo mide es `vault_norms --audit`, que
    # marca notas en `10_Migrated/` sin su `_report-*.md`.
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}
