"""PAT-7 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it. The faces are in `porque.md`.
"""

NORMA = {
    "code": "PAT-7",
    "distinguido_de": {
        "AP-05": (
            "AP-05 es el mismo dato con valores distintos sin que nadie lo "
            "decidiera: deuda. PAT-7 es el mismo dato con valores distintos "
            "que el autor declara como desacuerdo legítimo con `contradicts:`: "
            "información. Una tercera nota que discrepa sin declararlo sigue "
            "siendo AP-05."
        ),
        "PAT-1": (
            "PAT-1 resuelve la divergencia eligiendo una nota canónica. PAT-7 "
            "es para cuando no hay canónica todavía —dos fuentes que miden "
            "distinto, una evidencia sin cerrar— y elegir una borraría la "
            "decisión pendiente."
        ),
    },
    "name": "Desacuerdo legítimo declarado — contradicts entre notas",
    "type": "pattern",
    "category": "linking",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Cuando dos notas sostienen cosas incompatibles y el desacuerdo es "
        "legítimo, una de ellas lo declara en su frontmatter con el predicado "
        "de la ontología `contradicts` (`contradicts: [\"[[otra-nota]]\"]`). "
        "`vault_fuente_unica` deja de contar ese conflicto como deuda AP-05 y "
        "lo publica en `declared_disagreements`, y `vault_context_pack` "
        "entrega los dos lados cuando selecciona uno, con `disagrees_with`. "
        "Es la respuesta de la LLM Wiki de Karpathy a las contradicciones: el "
        "lint las señala, y las que son reales se conservan como tales en vez "
        "de resolverse eligiendo un ganador."
    ),
    "signal": (
        "Un conflicto de `vault_fuente_unica` cuyas notas están unidas por "
        "`contradicts:` sale en `declared_disagreements` y no en `conflicts`; "
        "un paquete que incluye una de las dos notas incluye la otra."
    ),
    "prevention": (
        "N/A — es el patrón correcto. No añade un valor de `status`: el "
        "vocabulario es cerrado y el desacuerdo es una relación entre dos "
        "notas, no un estado de una."
    ),
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_fuente_unica", "vault_context_pack"],
    "introduced_version": "v41.26",
    "revisado_en": "2026-11-16",
}
