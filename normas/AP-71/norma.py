"""AP-71 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-71",
    "name": "Concepto importante sin página propia",
    "type": "antipattern",
    "category": "linking",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "Un término que varias notas mencionan —un nombre propio de dos o "
        "más palabras o una sigla— no tiene ninguna nota que responda a él "
        "por nombre de fichero o `aliases:`. Cada nota lo explica a medias "
        "o lo da por sabido, y un agente que lo busca encuentra menciones "
        "dispersas en vez de una definición. Es el lint de la LLM Wiki de "
        "Karpathy: «conceptos importantes que se mencionan sin tener su "
        "propia página». No se infiere por parecido: solo cuenta lo que el "
        "texto marca como entidad, con la regla que ya usa la ingesta."
    ),
    "signal": (
        "El mismo término aparece en `UMBRAL_CONCEPTO` notas o más (fuera de "
        "bloques de código y de la documentación del estándar) y ningún "
        "fichero ni alias lo resuelve, ni literal ni como el slug que le "
        "daría `vault_write`. Un `title:` no lo resuelve (AP-44)."
    ),
    "prevention": (
        "`vault_audit` publica `conceptsWithoutPage` y convierte los más "
        "citados en `nextActions` con el `vault_write` que crea la página. "
        "Se salda escribiendo la página y enlazándola desde las notas que lo "
        "mencionan; un alias en una nota existente basta si esa nota ya es "
        "su definición. Sin penalización: es una sugerencia de qué escribir, "
        "no un defecto que reste salud."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "distinguido_de": {
        "PAT-8": (
            "AP-71 señala el concepto que varias notas mencionan y ninguna "
            "define. PAT-8 es cómo nace una página a partir de una pregunta "
            "ya respondida: la síntesis vuelve al wiki citando las notas de "
            "las que salió. Una página de PAT-8 puede saldar un AP-71, pero "
            "su origen es la consulta, no la mención repetida."
        ),
        "AP-05": (
            "AP-05 es el mismo dato con valores distintos en varias notas. "
            "AP-71 no compara valores: señala que el concepto no tiene dueño, "
            "que es la condición previa para que AP-05 aparezca."
        ),
    },
    "introduced_version": "v41.26",
    "revisado_en": "2026-11-16",
}
