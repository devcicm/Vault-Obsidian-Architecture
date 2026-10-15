"""AP-27 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-27",
    "distinguido_de": {
        "AP-26": (
            "Las dos son campos ausentes del frontmatter. AP-26 es `tags`, que "
            "clasifica de forma abierta y multiple; AP-27 es `type`, que asigna "
            "un único tipo y decide que otras normas aplican. Por eso AP-27 "
            "bloquea más cosas aguas abajo que AP-26."
        ),
    },
    "name": "Missing type field — nota sin tipo declarado",
    "type": "antipattern",
    "category": "metadata-completeness",
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Nota sin campo `type`. El tipo es lo que ancla la nota a su sección "
        "canónica (CN-02): sin él no se puede verificar la coincidencia "
        "type ↔ carpeta que sostiene la dimensión de exactitud (F4)."
    ),
    "signal": "vault_audit la cuenta en missing_type y penaliza -2 por nota (tope -10).",
    "prevention": (
        "vault_write deriva el type de la sección (vault_registry.section_default_type; "
        "en una sección propia, el primero de sus tipos declarados) o lo toma de "
        "vault_write --meta '{\"type\": ...}', y rechaza la nota que no tiene de dónde "
        "sacarlo. vault_move --type lo cambia al reclasificar, y "
        "vault_frontmatter_completar lo completa en notas que ya existen."
    ),
    "tools_enforcing": ["vault_write", "vault_frontmatter_completar"],
    # Hasta v41 `vault_validate` no miraba `type`. Desde v41 el contrato de
    # nota (`vault_contrato_nota`) lo exige a las notas de contenido, y
    # `vault_validate` lo reporta entre los campos que faltan; `vault_audit`
    # lo cuenta en `missing_type`, con peso propio.
    "tools_detecting": ["vault_audit", "vault_validate"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
