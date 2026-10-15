"""AP-25 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-25",
    "distinguido_de": {
        "AP-14": (
            "Las dos son referencias que no resuelven. AP-14 vive en el grafo de "
            "Obsidian —wikilinks entre notas—; AP-25 vive dentro de un diagrama "
            "mermaid, donde el nodo citado no está definido. El discriminador es "
            "el espacio de nombres en el que se busca el destino."
        ),
    },
    "name": "Mermaid diagram syntax errors — nodos/tipos no definidos",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos "
        "(unknown_type), nodos referenciados pero no definidos (undefined_node), "
        "flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se "
        "renderiza en Obsidian y pierde su valor documental."
    ),
    "signal": (
        "vault_audit detecta errores con vault_mermaid_check.scan_vault() y los reporta "
        "como AP-25 con penalización -2 por error. La nota se marca como mermaidError "
        "en el output del audit."
    ),
    "prevention": (
        "Validar con vault_mermaid_check antes de commit. Usar tipos conocidos "
        "(graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). "
        "Asegurar que cada nodo referenciado en una flecha exista como definición previa."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit", "vault_mermaid_check"],
    "introduced_version": "v34.2",
    "revisado_en": "2026-10-09",
}
