"""PAT-10 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it. The faces are in `porque.md`.
"""

NORMA = {
    "code": "PAT-10",
    "distinguido_de": {
        "PAT-9": (
            "PAT-9 genera el esquema de trabajo que el agente lee en cada sesión "
            "(carpetas, convenciones, protocolo). PAT-10 clasifica la lógica de "
            "negocio detectada en un proyecto en ocho operaciones universales y "
            "exige los nombres oficiales del catálogo de patrones arquitectónicos "
            "y de diseño."
        ),
        "AP-45": (
            "AP-45 prohíbe inventar contenido sin evidencia. PAT-10 lo aplica al "
            "análisis de código: cuando una capacidad no muestra señal verificable "
            "de operación, se declara `unclassified` en lugar de adivinar, y nunca "
            "se asignan nombres caseros fuera del catálogo oficial."
        ),
    },
    "name": "Taxonomía de operaciones de lógica de negocio y catálogo oficial de patrones",
    "type": "pattern",
    "category": "structure",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Todo escaneo de capacidades, flujos y patrones sobre un repositorio "
        "(propio o de terceros) clasifica cada capacidad en las ocho operaciones "
        "universales de lógica de negocio (`auth`, `rule`, `lifecycle`, "
        "`workflow`, `transform`, `event`, `integration`, `query` — o "
        "`unclassified` si falta evidencia verificable, AP-45), sin acoplar el "
        "estándar a un dominio concreto como ERP. Al mismo tiempo, cualquier "
        "patrón de diseño, arquitectura, concurrencia o resiliencia detectado o "
        "registrado debe usar su nombre oficial reconocido en la industria (GoF, "
        "Fowler PoEAA, Evans DDD, Hohpe EIP, Cockburn, Richards & Ford, Nygard) "
        "desde el catálogo canónico único (`patrones_diseno.CATALOGO_PATRONES`)."
    ),
    "signal": (
        "`vault_code_query --scan-path` y `vault_pattern_list --catalog/--scan-path` "
        "emiten `pattern: PAT-10`, etiquetando `business_operations` en el "
        "vocabulario cerrado de ocho operaciones y publicando patrones solo con "
        "su nombre oficial del catálogo."
    ),
    "prevention": (
        "N/A — es el patrón correcto. Un tercero o agente comprende la lógica "
        "de negocio de un proyecto por operaciones universales y nombres de "
        "patrón estándar sin ruido de normas internas del mantenedor ni nombres "
        "inventados."
    ),
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_code_query", "vault_pattern_list"],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-24",
}
