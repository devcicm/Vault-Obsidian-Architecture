"""PAT-2 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "PAT-2",
    "distinguido_de": {
        "AP-03": (
            "Miran el mismo stub desde los dos lados. AP-03 es el anti-patrón: el "
            "stub existe sin política que diga cuándo deja de serlo. PAT-2 es el "
            "patrón que la aporta: gradiente de enriquecimiento con umbrales. "
            "Saldar AP-03 es aplicar PAT-2; no son dos hallazgos sobre la misma "
            "nota."
        ),
    },
    "name": "Stub enrichment gradient",
    "type": "pattern",
    "category": "content-quality",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Un stub con ≥3 líneas reales se enriquece progresivamente en cada sesión que lo toca. "
        "La eliminación solo aplica a skeletons (AP-11) y deceptive skeletons (AP-20)."
    ),
    "signal": "Stubs del vault tienen status:stub y fecha expand_by.",
    "prevention": "N/A — es el patrón correcto.",
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_graph_fix", "vault_audit"],
    "introduced_version": "v25",
    "revisado_en": "2026-10-09",
}
