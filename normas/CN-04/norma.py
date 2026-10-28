"""CN-04 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "CN-04",
    "distinguido_de": {
        "CN-01": (
            "CN-01 fija cómo se llama el fichero; CN-04, cómo se presenta la "
            "nota al abrirla. El nombre lo lee quien navega el árbol; el H1, "
            "quien ya está dentro del documento."
        ),
        "AP-45": (
            "AP-45 mide si el cuerpo tiene evidencia; CN-04, si dice qué es. "
            "Un H1 no es contenido: la nota que solo tiene título sigue siendo "
            "AP-45."
        ),
        "CN-05": (
            "CN-04 fija cómo abre una nota; CN-05, quién es el dueño de un "
            "cuerpo de código. Una es convención de escritura y la otra de "
            "estructura del repo: no se solapan ni se contradicen."
        ),
    },
    "name": "Note opens with its title — la nota abre con su título como H1",
    "type": "antipattern",
    "category": "convention",
    "severity": "low",
    "enforcement": "guard",
    "description": (
        "El cuerpo de una nota empieza con su título como encabezado H1. Hasta "
        "v40.34 `vault_write`, `vault_knowledge_save` y `vault_ai_decision` lo "
        "dejaban solo en el frontmatter, y la nota abierta fuera de Obsidian "
        "—un editor de texto, un visor de Markdown, un diff— empezaba en la "
        "primera frase o en una línea de metadatos sin decir qué era. El vault "
        "tiene que seguir siendo legible sin la herramienta que lo generó."
    ),
    "signal": "La primera línea no vacía del cuerpo no es un `# Título`.",
    "prevention": (
        "Escribir por las tools: `vault.kernel.contenido.con_titulo` antepone el "
        "H1 y respeta uno que ya venga."
    ),
    "tools_enforcing": ["vault_write", "vault_knowledge_save", "vault_ai_decision"],
    # v41.2: `vault_audit` lo mide en las notas ya escritas, con el mismo
    # criterio (`abre_con_h1`), en `issues.cn04NoTitle` y sin peso. El
    # enforcement sigue `guard` hasta que el usuario decida si penaliza.
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v40.35",
    "revisado_en": "2026-10-09",
}
