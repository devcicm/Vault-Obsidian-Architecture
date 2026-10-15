"""AP-09 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-09",
    "distinguido_de": {
        "CN-02": (
            "CN-02 es la convención general de destino: las secciones numeradas "
            "son los únicos sitios válidos. AP-09 es su incumplimiento con nombre "
            "para un tipo concreto: los runbooks fuera de la estructura. Se "
            "separa porque el runbook tiene además exigencias de contenido que "
            "CN-02 no mira."
        ),
    },
    "name": "Runbooks fuera de estructura",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) "
        "en lugar de 06_Runbooks/. Dificulta la localización en incidentes."
    ),
    "signal": "Notas con title que contiene 'runbook', 'procedure', 'how-to' fuera de 06_Runbooks/.",
    "prevention": "Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}
