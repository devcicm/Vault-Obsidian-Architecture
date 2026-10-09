"""AP-03 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-03",
    "distinguido_de": {
        "PAT-2": (
            "Miran el mismo stub desde los dos lados. AP-03 es el anti-patrón: el "
            "stub existe sin política que diga cuándo deja de serlo. PAT-2 es el "
            "patrón que la aporta: gradiente de enriquecimiento con umbrales. "
            "Saldar AP-03 es aplicar PAT-2; no son dos hallazgos sobre la misma "
            "nota."
        ),
    },
    "name": "Stubs sin política de expansión",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Nota con contenido real pero incompleto (≥3 líneas reales) sin fecha de expansión. "
        "Distinción con AP-11: AP-03 tiene información útil, AP-11 no tiene ningún contenido real."
    ),
    "signal": "vault_audit reporta notas con status:stub sin campo expand_by o con expand_by vencido.",
    "prevention": "Agregar meta: {status: stub, expand_by: YYYY-MM-DD} al crear stubs. Enriquecer en cada sesión.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v19",
}
