"""AP-80 — Arista de grafo sin sello epistémico (EXTRACTED / INFERRED / AMBIGUOUS).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "AP-80",
    "distinguido_de": {
        "PAT-11": (
            "AP-80 exige que cada arista materializada en el grafo lleve sello "
            "epistémico verificable (`EXTRACTED`, `INFERRED` o `AMBIGUOUS`) y "
            "`confidence` en `[0.0, 1.0]`. PAT-11 gobierna el patrón de consulta "
            "que consume ese grafo (`--report`, `--explain`, `--path`) antes de "
            "lanzar búsquedas ciegas sobre archivos crudos."
        ),
    },
    "name": "Arista de grafo sin sello epistémico ni confianza",
    "type": "antipattern",
    "category": "linking",
    "severity": "medium",
    "enforcement": "guard",
    "description": (
        "Mezclar enlaces verificados en disco (`wiki_link`, `implements`, "
        "`supersedes`) con relaciones inferidas por heurística (`shared_tag`, "
        "`same_section`, `mentions`) o sugerencias ambiguas sin distinguir su "
        "origen lleva al agente a tratar conjeturas como hechos (AP-45). Cada "
        "arista consolidada en `99_Index/graph.json`, `graph-enriched.json` y "
        "`vault_subgraph` debe declarar `epistemic` en el vocabulario cerrado "
        "`('EXTRACTED', 'INFERRED', 'AMBIGUOUS')` y `confidence` en `[0.0, 1.0]`."
    ),
    "signal": (
        "Una arista del grafo carece de `epistemic` en `CONFIANZA_EPISTEMICA` "
        "o de `confidence` numérico acotado, impidiendo filtrar relaciones "
        "extraídas de heurísticas."
    ),
    "prevention": (
        "Consolidar toda arista a través del dueño único "
        "`vault.grafo.aristas.consolidar_aristas` / `clasificar_arista_epistemica` "
        "y proyectar `stats.epistemic` desde `vault.grafo.refresco.ensamblar_grafo`."
    ),
    "tools_enforcing": ["vault_graph", "vault_subgraph"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-26",
}
