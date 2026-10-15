"""AP-34 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-34",
    "distinguido_de": {
        "AP-14": (
            "AP-14 es el wikilink sin destino; AP-34 es la relación tipada cuyo "
            "endpoint no existe. La misma ausencia en dos capas: la sintáctica "
            "del enlace y la semántica del grafo de predicados. Una nota puede "
            "tener AP-34 con todos sus wikilinks intactos."
        ),
    },
    "name": "Relacion tipada huerfana — endpoint inexistente en el vault",
    "type": "antipattern",
    "category": "linking",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Una relacion tipada (entity o code) referencia un endpoint que no existe "
        "como nota en el vault. Ej: relacion `User -- has_many --> Order` donde "
        "no existen `User.md` ni `Order.md`. El grafo enriquecido tendra edges "
        "hacia nodos fantasma que nunca resolveran."
    ),
    "signal": (
        "vault_audit detecta orphan_typed_relations[] listando la relacion y "
        "los endpoints faltantes. vault_graph_merge reporta unresolved_entities[]."
    ),
    "prevention": (
        "SP-02: verificar que los endpoints existan antes de registrar la relacion. "
        "Ejecutar vault_search o vault_list para confirmar que las notas "
        "referenciadas en fromEntity/toEntity existen en el vault."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit", "vault_graph_merge"],
    "introduced_version": "v37",
    "revisado_en": "2026-10-09",
}
