"""AP-23 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-23",
    "distinguido_de": {
        "AP-11": (
            "Son los dos extremos del mismo eje. AP-11 es defecto de contenido "
            "—la nota no dice nada—; AP-23 es exceso —la nota supera el techo de "
            "complejidad y debería partirse—. Ninguna nota puede incurrir en las "
            "dos."
        ),
    },
    "name": "Note complexity ceiling — nota demasiado larga",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener "
        "y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas "
        "interconectadas con [[wiki-links]] desde la nota original."
    ),
    "signal": "vault_write advierte en la respuesta con ap23_warning cuando content > 500 líneas. "
    "vault_norms --scan reporta AP-23 en notas largas.",
    "prevention": (
        "Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección "
        "con [[sub-nota|título]]. La nota original actúa como índice/resumen."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_write", "vault_norms"],
    "introduced_version": "v30",
}
