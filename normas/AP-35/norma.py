"""AP-35 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-35",
    "distinguido_de": {
        "AP-31": (
            "AP-31 mira la arista —le falta tipo—; AP-35 mira el conjunto —hay "
            "varios sistemas de relaciones que no se hablan entre si—. Un vault "
            "puede tener todas sus aristas tipadas y aun así estar en silos, y al "
            "revés."
        ),
    },
    "name": "Silos de relacion — sistemas de grafos aislados",
    "type": "antipattern",
    "category": "structure",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "El vault mantiene tres sistemas de relaciones en silos aislados: "
        "(a) wiki-links en graph.json, (b) entity relations en "
        "06_Diagrams/entity/*-relations.json, (c) code relations en "
        "11_Code/.code-index.json. Ninguno de estos sistemas se integra "
        "con los otros, produciendo un grafo de conocimiento fragmentado. "
        "vault_impact y BFS solo ven wiki-links, ignorando relaciones "
        "semanticas ricas registradas en los otros sistemas."
    ),
    "signal": (
        "vault_audit reporta silo_flags[]: entity_relations sin mergear "
        "(AP-35-entity), code_relations sin mergear (AP-35-code), y "
        "graph_enriched_outdated si el enriquecido tiene >24h."
    ),
    "prevention": (
        "Ejecutar vault_graph_merge periodicamente (recomendado: cada sesion "
        "o cada vez que se registren nuevas relaciones). vault_graph --typed "
        "genera graph-enriched.json que unifica los tres sistemas."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit", "vault_graph_merge"],
    "introduced_version": "v37",
}
