"""AP-72 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-72",
    "name": "Comentario que cita una decisión que no existe",
    "type": "antipattern",
    "category": "linking",
    "severity": "medium",
    "enforcement": "guard",
    "description": (
        "Un comentario del código dice el porqué apuntando a la decisión que "
        "lo registra —`ADR-NNNN` en este repositorio, `@vault: 03_Decisions/…` "
        "en un proyecto con vault— y esa decisión no existe. El lector sigue "
        "la cita y no encuentra nada: el porqué se perdió y el código sigue "
        "afirmando que está escrito. Es la regla de Torti Code «el comentario "
        "dice el porqué y apunta al ADR» aplicada a lo único decidible de "
        "ella: que el destino exista."
    ),
    "signal": (
        "En el repositorio, un `ADR-NNNN` en el código (`scripts/`, `vault/`, "
        "`cli/`, `tests/`, `normas/`, `mcp/`) sin `docs/adr/NNNN-*.md`. En un "
        "vault, un `@vault:` del código que apunta a `03_Decisions/` y no "
        "resuelve a una decisión (`es_adr`) que exista."
    ),
    "prevention": (
        "`vault_doc_sync --check` lista cada cita rota como `adr_sin_fichero` "
        "y la puerta falla. Se salda escribiendo el ADR que falta o corrigiendo "
        "la cita al número que existe. En un vault, `vault_code_sync` acepta "
        "como destino de `@vault:` una decisión de `03_Decisions/` que existe y "
        "sigue dando por huérfana la que no."
    ),
    "tools_enforcing": ["vault_doc_sync"],
    "tools_detecting": ["vault_code_sync"],
    "distinguido_de": {
        "AP-07": (
            "AP-07 mide que un ADR que existe tenga sus secciones. AP-72 mide "
            "que el ADR que el código cita exista; no lee su contenido."
        ),
    },
    "introduced_version": "v41.26",
    "revisado_en": "2026-11-16",
}
