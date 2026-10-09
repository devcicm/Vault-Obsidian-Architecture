"""AP-32 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-32",
    "distinguido_de": {
        "AP-31": (
            "AP-31 es la arista sin `predicate`: la relación existe y no dice de "
            "que tipo es. AP-32 tiene predicate, pero no pertenece a la ontología "
            "declarada. El discriminador es si el campo está presente: ausencia "
            "frente a valor fuera de vocabulario."
        ),
        "AP-33": (
            "Las dos son predicados que la ontología no acepta tal cual. AP-32 es "
            "el predicado desconocido, sin equivalente canónico. AP-33 es el "
            "sinónimo: existe un canónico al que normalizar, y por eso se repara "
            "sin perder información. El discriminador es si hay destino de "
            "normalización."
        ),
    },
    "name": "Relaciones tipadas sin predicate valido en la ontologia",
    "type": "antipattern",
    "category": "linking",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Una relacion registrada en entity relations o code relations usa un "
        "relationType/type que no existe en vault-ontology.json. Esto produce "
        "edges que no pueden interpretarse semanticamente en el grafo enriquecido. "
        "Ej: relationType='inherits' cuando el predicate canonico es 'extends'."
    ),
    "signal": (
        "vault_graph_merge reporta unknown_predicates[] con el predicate invalido "
        "y la fuente (entity/code). Sugiere el predicate canonico mas cercano."
    ),
    "prevention": (
        "Usar solo predicates del vocabulario canonico en vault-ontology.json. "
        "Para entity relations: has_one, has_many, belongs_to, many_to_many, "
        "implements, extends, depends_on, uses, calls, owns, aggregates. "
        "Para code relations: imports, extends, implements, calls, uses, re-exports, depends_on."
    ),
    "tools_enforcing": [],
    # `vault_audit` pesa AP-31, AP-34 y AP-35 del grafo, no AP-32: no hay
    # entrada suya en PENALIZACIONES. El predicate fuera de ontología lo
    # reporta `vault_graph_merge` en `unknown_predicates`.
    "tools_detecting": ["vault_graph_merge"],
    "introduced_version": "v37",
}
