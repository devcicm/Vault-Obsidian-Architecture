"""AP-62 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-62",
    "name": "El consumidor paga el fan-out del productor",
    "type": "antipattern",
    "category": "architecture",
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Un módulo importa a otro **solo para leer un recurso** —una tabla "
        "constante, una función pura— y con el import se lleva todas las "
        "dependencias del productor. Cuando los dos están en contextos "
        "distintos, la arquitectura registra un cruce de frontera de "
        "negocio donde lo único que ocurrió fue **leer un dato**.\n\n"
        "El caso que le dio nombre no se buscó: se tropezó con él en "
        "v40.27. De los veinticuatro importadores de `vault_norms`, "
        "**veintiuno solo querían datos** —`NORM_CATALOG`, `STATUS_VOCAB`, "
        "`status_frontmatter_lines`— y entraban por una fachada que "
        "reexporta el motor de auditoría y sus once dependencias. Mudado el "
        "catálogo a una hoja del núcleo y repuntados los importadores, los "
        "cruces del repo pasaron de **62 a 42** sin que se eliminara una "
        "sola capacidad.\n\n"
        "Lo caro es que **cada sitio, por separado, parece razonable**: "
        "quien escribe `from vault_norms import STATUS_VOCAB` no está "
        "haciendo nada mal, y ningún guard tenía por qué ponerse rojo. El "
        "daño solo existe en el agregado, y por eso hace falta medirlo en "
        "vez de revisarlo — que es la forma exacta que tiene el deterioro "
        "por acumulación."
    ),
    "signal": (
        "Un módulo con fan-out alto cuyos importadores solo le piden "
        "constantes; una fachada que reexporta a la vez el catálogo y el "
        "motor que lo consume; un cruce de contexto cuya única razón de ser "
        "es un `from X import UNA_CONSTANTE`."
    ),
    "prevention": (
        "`vault_recursos --check --strict` clasifica cada arista del grafo "
        "y cuenta como deuda la que cumple las cuatro condiciones: el "
        "destino no está en el núcleo, tiene fan-out mayor que cero, todo "
        "lo que el origen le pide es recurso, y los dos están en contextos "
        "distintos. `--ranking` ordena los productores por cuántos cruces "
        "colapsaría mudar cada uno, que es lo que convierte la medida en un "
        "plan.\n\n"
        "Se salda **dándole al recurso un dueño con forma de hoja**: partir "
        "el productor en catálogo y motor, y repuntar a los consumidores al "
        "dueño. La lección de v40.27 es que **partir el fichero por sí solo "
        "no mueve una sola cifra** — la arquitectura no cambia hasta que "
        "los importadores dejan de entrar por la fachada.\n\n"
        "Límites declarados: mide `from X import y` y no `import X`, porque "
        "quien importa el módulo entero no declara qué usa; decide la "
        "pureza por AST a punto fijo, así que una función que dependa de un "
        "global mutable pasará por pura; y da las clases por acopladas sin "
        "mirarlas, prefiriendo no contar un sitio a contar uno que no lo es."
    ),
    "tools_enforcing": ["vault_recursos"],
    "tools_detecting": ["vault_recursos"],
    "distinguido_de": {
        "AP-57": (
            "AP-57 es el criterio escrito dos veces sin dueño; AP-62 es el "
            "criterio con un dueño perfectamente claro al que se llega por "
            "el camino caro. Son opuestos en el síntoma: AP-57 aparece "
            "cuando alguien **no** importó al dueño y reimplementó, AP-62 "
            "cuando sí lo importó y el dueño estaba envuelto en un módulo "
            "que arrastra. Y por eso la corrección de AP-62 no puede ser "
            "copiar el recurso al consumidor: eso lo cambia por un AP-57."
        ),
        "AP-58": (
            "Los dos hablan de imports, pero AP-58 mide el **ciclo** —el "
            "destino vuelve al origen— y AP-62 mide el **peso** —el destino "
            "arrastra más de lo que hacía falta—. Un arrastre puede no "
            "cerrar ningún ciclo y seguir siendo deuda, y un ciclo puede "
            "darse entre dos módulos que se piden justo lo que necesitan. "
            "Se cruzan al saldarlos: mudar el recurso a una hoja rompió de "
            "paso quince ciclos diferidos en v40.27, y ese efecto fue una "
            "consecuencia medida, no el objetivo."
        ),
        "AP-59": (
            "AP-59 vigila la **forma del núcleo**: que lo declarado núcleo "
            "lo parezca al medirlo. AP-62 vigila **quién paga por quién** "
            "fuera de él. Se necesitan mutuamente y en direcciones "
            "opuestas: la corrección típica de AP-62 es mudar un recurso al "
            "núcleo, y AP-59 es lo único que impide que esa mudanza sea una "
            "reclasificación de conveniencia para bajar la cifra."
        ),
    },
    "introduced_version": "v40.28",
    "revisado_en": "2026-10-09",
}
