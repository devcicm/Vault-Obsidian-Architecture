"""PAT-6 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "PAT-6",
    "distinguido_de": {
        "AP-31": (
            "AP-31 es el defecto: aristas sin predicate. PAT-6 es el patrón que "
            "lo cierra: enriquecimiento semántico periodico del grafo. Saldar "
            "AP-31 una vez no basta si PAT-6 no se ejecuta; PAT-6 sin AP-31 "
            "pendiente sigue siendo útil."
        ),
    },
    "name": "Semantic graph enrichment — enriquecimiento periodico del grafo",
    "type": "pattern",
    "category": "linking",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Ejecutar vault_graph --typed al final de cada sesion productiva para "
        "generar graph-enriched.json con predicates semanticos unificados. "
        "El grafo enriquecido combina wiki-links, entity relations y code relations "
        "en un solo grafo consultable con filtros por predicate, cardinalidad "
        "y tipo de nodo. Esto habilita busquedas de conocimiento semanticas "
        "y analisis de impacto con tipos."
    ),
    "signal": "graph-enriched.json existe y tiene updated_at < 24 horas.",
    "prevention": (
        "N/A — es el patron correcto. Agregar vault_graph --typed al session "
        "protocol como paso automatico antes de vault_audit."
    ),
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_graph_merge", "vault_audit"],
    "introduced_version": "v37",
}
