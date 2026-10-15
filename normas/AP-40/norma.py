"""AP-40 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-40",
    "distinguido_de": {
        "AP-43": (
            "AP-40 es la contradicción visible: el contrato publicado acepta algo "
            "que la CLI rechaza. AP-43 es la ausencia: la norma existe y el punto "
            "de uso no la menciona ni la aplica. El discriminador es si hay dos "
            "afirmaciones en conflicto o solo una sin refuerzo."
        ),
    },
    "name": "Contrato publicado que la CLI rechaza",
    "type": "antipattern",
    "category": "consistency",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Una tool publica en su catálogo parámetros que su propio argparse no "
        "acepta. La tool aparece en tools/list, se puede invocar, y falla "
        "siempre con 'unrecognized arguments'. Medido en v39: 45 de 82 tools "
        "conciliables publicaban al menos un param inexistente — más de la "
        "mitad de la superficie MCP era inalcanzable sin que nada lo señalara, "
        "porque el guard de sincronía comparaba el JSON contra el Python: dos "
        "copias de la misma equivocación coinciden perfectamente."
    ),
    "signal": (
        "Invocar la tool por MCP devuelve 'unrecognized arguments'; el nombre "
        "de un param del catálogo no aparece como flag largo en el script."
    ),
    "prevention": (
        "El contrato de argumentos lo declara argparse, no el catálogo: "
        "vault_mcp_catalog.argparse_params() lee los add_argument del script y "
        "reconciled_params() publica solo lo que la CLI acepta, conservando la "
        "descripción escrita a mano cuando el nombre coincide. "
        "vault_mcp_catalog --check-params audita el JSON ya generado (que es lo "
        "que el servidor consume) contra el argparse real."
    ),
    "tools_enforcing": ["vault_mcp_catalog"],
    "tools_detecting": ["vault_mcp_catalog", "vault_norms"],
    "introduced_version": "v39",
    "revisado_en": "2026-10-09",
}
