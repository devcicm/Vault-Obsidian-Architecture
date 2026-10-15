"""AP-26 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-26",
    "distinguido_de": {
        "AP-27": (
            "Las dos son campos ausentes del frontmatter. AP-26 es `tags`, que "
            "clasifica de forma abierta y multiple; AP-27 es `type`, que asigna "
            "un único tipo y decide que otras normas aplican. Por eso AP-27 "
            "bloquea más cosas aguas abajo que AP-26."
        ),
        "AP-30": (
            "Las dos clasifican la nota. AP-26 lo hace por tema, con `tags` "
            "libres; AP-30 lo hace por sensibilidad, con la tríada CIA y valores "
            "tasados. Un tag `confidencial` no salda AP-30."
        ),
    },
    "name": "Missing tags — nota de contenido sin tags",
    "type": "antipattern",
    "category": "metadata-completeness",
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Nota de contenido sin campo `tags` o con la lista vacía. Sin tags la nota "
        "es invisible para la búsqueda por facetas y no participa en los edges "
        "shared_tag del grafo: queda alcanzable solo por wiki-link directo."
    ),
    "signal": (
        "vault_audit la cuenta en missing_tags y penaliza -2 por nota (tope -15). "
        "Aparece en el resumen como 'N sin tags AP-26'."
    ),
    "prevention": (
        "vault_write rechaza la nota de contenido sin tags (missing_tags; las de "
        "índice y las de 00_System están exentas): se pasan con vault_write --tags. "
        "vault_ingest y vault_preferences los derivan del origen y la categoría, y "
        "vault_frontmatter_completar los completa en notas que ya existen."
    ),
    "tools_enforcing": ["vault_write", "vault_ingest", "vault_preferences",
                        "vault_frontmatter_completar"],
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
