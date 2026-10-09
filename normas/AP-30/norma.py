"""AP-30 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-30",
    "distinguido_de": {
        "AP-26": (
            "Las dos clasifican la nota. AP-26 lo hace por tema, con `tags` "
            "libres; AP-30 lo hace por sensibilidad, con la tríada CIA y valores "
            "tasados. Un tag `confidencial` no salda AP-30."
        ),
        "AP-29": (
            "Las dos son campos ausentes. AP-29 es `status`, el estado del ciclo "
            "de vida, que cambia con el tiempo. AP-30 es la clasificación CIA, "
            "que describe la sensibilidad del contenido y no cambia por avanzar "
            "el trabajo. El discriminador es si el valor es temporal o "
            "intrínseco."
        ),
    },
    "name": "Missing CIA classification — nota sin clasificación de la tríada",
    "type": "antipattern",
    "category": "metadata-completeness",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Nota sin `cia_integrity` / `cia_availability` / `cia_sensitivity`. Sin "
        "clasificación CIA la nota no puede endurecer su umbral de actualidad "
        "(30d → 15d en critical|high) ni ponderar su peso en el health score: el "
        "pilar del estándar queda sin aplicar sobre ella."
    ),
    "signal": "vault_audit la cuenta en missing_cia y penaliza -2 por nota (tope -15).",
    "prevention": (
        "Declarar los tres ejes en la escritura. vault_ingest asigna "
        "cia_integrity: low a lo ingerido por no estar verificado."
    ),
    "tools_enforcing": ["vault_ingest", "vault_frontmatter_completar"],
    # `vault_quality_check` valida los valores CIA **cuando están** (`if
    # "cia_integrity" in fm`); la ausencia, que es lo que AP-30 nombra, no la
    # ve. La cuenta `vault_audit` en `missing_cia`.
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v30",
}
