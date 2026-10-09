"""AP-47 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-47",
    "name": "Artefacto derivado desfasado — el índice dejó de reflejar el disco",
    "type": "antipattern",
    "category": "consistency",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "El vault es la fuente de verdad y `search-index.json` y `graph.json` "
        "son proyecciones suyas. Una escritura que no pasa por `vault_write` "
        "—un agente remoto, una tool que escribe la nota y no toca el índice, "
        "una copia a mano— deja la proyección atrás, y a partir de ahí el "
        "agente busca sobre un mapa viejo: la nota existe y `vault_search` no "
        "la encuentra, así que la vuelve a escribir. La duplicación no es un "
        "descuido del agente, es la consecuencia lógica de un índice que "
        "miente.\n\n"
        "El estándar no lleva base de datos por decisión normativa, y con "
        "consistencia eventual el desfase es esperable. Lo que no es "
        "aceptable es que **nadie lo mida**: `vault_reindex --check` "
        "comprobaba `len(notes) > 0`, de modo que un índice con una entrada "
        "sobre un vault de 300 notas pasaba la puerta."
    ),
    "signal": (
        "`vault_reindex --check` devuelve `index_stale`; el conteo de `.md` en "
        "las secciones canónicas no coincide con las entradas de "
        "`search-index.json`; `vault_search` devuelve 0 resultados sobre una "
        "nota que está en disco; `graph.json` tiene menos nodos que notas."
    ),
    "prevention": (
        "`vault_reindex --check` contrasta disco contra índice con el mismo "
        "criterio con el que reconstruye —una sola función, `_notas_en_disco()`, "
        "para que la comprobación y el arreglo no puedan medir cosas distintas "
        "(AP-44)— y reporta las dos direcciones: notas invisibles para la "
        "búsqueda y entradas que apuntan a ficheros que ya no están. El "
        "remedio es `vault_reindex`, y por eso la norma se audita en vez de "
        "bloquear: el desfase es un estado a reconciliar, no una escritura a "
        "rechazar."
    ),
    "tools_enforcing": ["vault_reindex", "vault_write"],
    "tools_detecting": ["vault_norms", "vault_reindex"],
    "distinguido_de": {
        "AP-59": (
            "AP-47 es la **cifra** escrita a mano en la documentación; AP-59 "
            "es su versión estructural, la **lista** escrita a mano en el "
            "código. Comparten disciplina —derivar en vez de escribir— y por "
            "eso los umbrales de AP-59 no pueden ser literales sin cometer "
            "AP-47 dentro de AP-59."
        ),
    },
    "introduced_version": "v39.3",
}
