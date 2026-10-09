"""AP-31 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-31",
    "distinguido_de": {
        "AP-32": (
            "AP-31 es la arista sin `predicate`: la relación existe y no dice de "
            "que tipo es. AP-32 tiene predicate, pero no pertenece a la ontología "
            "declarada. El discriminador es si el campo está presente: ausencia "
            "frente a valor fuera de vocabulario."
        ),
        "AP-35": (
            "AP-31 mira la arista —le falta tipo—; AP-35 mira el conjunto —hay "
            "varios sistemas de relaciones que no se hablan entre si—. Un vault "
            "puede tener todas sus aristas tipadas y aun así estar en silos, y al "
            "revés."
        ),
        "PAT-6": (
            "AP-31 es el defecto: aristas sin predicate. PAT-6 es el patrón que "
            "lo cierra: enriquecimiento semántico periodico del grafo. Saldar "
            "AP-31 una vez no basta si PAT-6 no se ejecuta; PAT-6 sin AP-31 "
            "pendiente sigue siendo útil."
        ),
    },
    "name": "Grafo sin tipos semanticos — edges sin predicate explícito",
    "type": "antipattern",
    "category": "linking",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Todas las aristas del grafo usan el mismo tipo 'wiki-link' sin distinguir "
        "semántica: depends_on, implements, extends, calls, documents, etc. "
        "Sin predicates tipados, el analisis de impacto y las busquedas semanticas "
        "no pueden filtrar por tipo de relacion. "
        "La solucion es mergear las relaciones de entidad (vault_relation_add) y "
        "codigo (vault_code_relation) en el grafo para enriquecerlo con predicates."
    ),
    "signal": (
        "vault_audit detecta edges sin predicate o con predicate='wiki-link' como "
        "unico tipo en graph.json. Penaliza -3 por cada 100 edges sin predicates "
        "tipados (solo si existen relaciones de entidad o codigo sin mergear)."
    ),
    "prevention": (
        "Ejecutar vault_graph --typed o vault_graph_merge periodicamente para "
        "enriquecer el grafo con predicates. Toda relacion registrada via "
        "vault_relation_add o vault_code_relation debe reflejarse en graph-enriched.json."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit", "vault_graph_merge"],
    "introduced_version": "v37",
}
