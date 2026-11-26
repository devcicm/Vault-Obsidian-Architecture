"""PAT-11 — Navegación Grafo primero (`--report`, `--explain`, `--path`).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "PAT-11",
    "distinguido_de": {
        "AP-80": (
            "AP-80 exige que cada arista del grafo lleve sello epistémico y "
            "confianza verificables. PAT-11 es el patrón positivo de navegación "
            "estructurada (`vault_subgraph --report`, `--explain`, `--path` y "
            "guía en `vault_preferences --adapters`) que ahorra tokens antes de "
            "recurrir a barridos ciegos con grep/Glob."
        ),
    },
    "name": "Navegación Grafo primero y análisis estructural compacto",
    "type": "pattern",
    "category": "linking",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Antes de lanzar búsquedas amplias sobre decenas de archivos crudos "
        "quemando ventana de contexto, el agente consulta el reporte estructural "
        "compacto (`vault_subgraph --report`: God Nodes, comunidades y puentes), "
        "explica nodos clave (`--explain`) o traza rutas mínimas (`--path A B`). "
        "`vault_preferences --adapters` publica la directiva 'Grafo primero' en "
        "los adaptadores generados para clientes externos."
    ),
    "signal": (
        "`vault_subgraph --report`, `--explain` y `--path` devuelven mapas "
        "compactos con etiquetas epistémicas; `vault_preferences --adapters` "
        "incluye la cláusula 'Grafo primero (PAT-11)'."
    ),
    "prevention": (
        "N/A — es el patrón correcto. Reduce el consumo de tokens de exploración "
        "manteniendo 100 % ejecución local en Python stdlib sin BD ni embeddings."
    ),
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_subgraph", "vault_graph", "vault_preferences"],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-26",
}
