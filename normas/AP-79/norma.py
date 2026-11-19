"""AP-79 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-79",
    "name": "Nota sin entrada autosuficiente",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "Una nota que abre con una o tres líneas cortas obliga a quien no "
        "estuvo en la conversación que la escribió —un auditor humano, un "
        "agente externo— a reconstruir el contexto antes de entenderla. La "
        "nota escalonada lo evita como un artículo de enciclopedia: una "
        "entrada (lead) de dos a cuatro oraciones que se sostiene sola —qué "
        "es, por qué importa, en qué estado está, de dónde sale— y debajo "
        "las capas que crecen con el conocimiento: `## Contexto` (síntesis, "
        "antecedentes, relaciones), `## Detalle` (desarrollo, evidencia, "
        "consecuencias) y `## Fuentes`. El informe corto de dos o tres "
        "líneas solo vale para un registro de evento, y siempre enlaza con "
        "la nota completa de la que forma parte."
    ),
    "signal": (
        "`vault_audit` mide cada nota del vault con "
        "`vault.kernel.contenido.profundidad_de_nota`: una nota de artículo "
        "sin entrada autosuficiente (menos de `LEAD_MIN_ORACIONES` oraciones "
        "o de `LEAD_MIN_PALABRAS` palabras reales entre su H1 y su primer "
        "encabezado), o un registro de evento —sección cuya clase de "
        "documento es `registro`— sin entrada ni ningún wikilink. Quedan "
        "fuera los andamios, las plantillas (`status: template`), los "
        "índices, `00_System/` y las fuentes archivadas (AP-73), que se "
        "conservan como llegaron."
    ),
    "prevention": (
        "Escribir primero la entrada y después las capas, solo cuando hay "
        "algo que decir en ellas: lo que todavía falta se declara en la nota "
        "como esbozo (`status: stub` con `expand_by`, PAT-2) y no se rellena "
        "(AP-45). Un registro de evento corto enlaza con su nota padre. "
        "`vault_audit` publica la profundidad en `notesDepth` (recuento por "
        "nivel, por tipo y la mediana de palabras de la entrada), la lista "
        "en `issues.notesWithoutLead` y las primeras en `nextActions` "
        "(categoría `note_without_lead`).\n\n"
        "Límites declarados: la norma sabe que la entrada existe y tiene "
        "cuerpo, no que sea cierta ni que resuma bien la nota; las notas que "
        "ya existían se informan para subirlas, nunca se rechazan, y "
        "`vault_write` no gana ninguna puerta nueva."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "distinguido_de": {
        "AP-45": (
            "AP-45 pregunta si el cuerpo tiene evidencia; AP-79, si un lector "
            "sin contexto entiende la nota desde su primera línea. Una nota "
            "con evidencia y sin entrada cumple AP-45 y sigue en AP-79; una "
            "entrada larga sin nada debajo no salda AP-45."
        ),
        "AP-03": (
            "AP-03 es el esbozo sin plazo para crecer; AP-79, la nota sin "
            "entrada. Un esbozo escalonado —entrada, lo que falta declarado y "
            "`expand_by`— cumple las dos: crece por capas en vez de "
            "rellenarse."
        ),
        "CN-04": (
            "CN-04 fija que la nota abre con su título como H1; AP-79, que "
            "debajo del título haya una entrada que diga qué es. El H1 nombra "
            "la nota; la entrada la explica."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-19",
}
