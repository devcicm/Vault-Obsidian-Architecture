"""AP-57 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-57",
    "name": "Criterio con dueño, reimplementado en la medida",
    "type": "antipattern",
    "category": "architecture",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Un **criterio** —qué cuenta como instantánea congelada, qué es "
        "documentación del estándar y no una nota, qué es código y no un "
        "enlace— tiene un dueño canónico en el toolkit, y otro módulo lo "
        "vuelve a decidir por su cuenta con un `if` local.\n\n"
        "No es AP-50, que habla de **patrones regex** y de vocabularios: "
        "aquellos son datos que alguien puede leer y comparar. Un criterio "
        "vive enterrado en una condición, así que la copia sobrevive años "
        "sin que nadie la vea, y el día que el dueño cambia solo cambia el "
        "dueño. `vault_graph_fix` llevaba su propio `skip_set` de "
        "instantáneas y ya divergía de `vault_io.SNAPSHOT_DIRS`; como esa "
        "tool **escribe**, la divergencia no inflaba una métrica: reparaba "
        "dentro de una instantánea, que es dejar de serlo.\n\n"
        "Sale de v40.12: cuatro defectos de `vault_foreign_check` "
        "arreglados en una tanda, los cuatro con la misma forma —el "
        "registro canónico existía y la tool no lo consultaba—. Uno de "
        "ellos tenía el sentido de error peligroso: resolver destinos por "
        "basename ponía la medida **verde** justo donde Obsidian pinta el "
        "enlace roto. La regla 4 pide norma, no cuatro parches."
    ),
    "signal": (
        "Un módulo que clasifica notas escribe una constante distintiva de "
        "otro —`\".history\"`, el nombre del manifiesto, la valla de un "
        "fence— sin importar el símbolo que la posee.\n\n"
        "**Y su forma más cara: la copia al otro lado de una frontera de "
        "lenguaje** (v40.19). Un `.mjs`, un workflow de CI o un `Makefile` "
        "no pueden importar un registro Python, así que reescriben la "
        "decisión — y ningún guard que solo lea `*.py` puede verlo. La CI de "
        "este repo listaba a mano seis puertas de las diecisiete del "
        "registro: once no se ejecutaban en ningún PR, y nada estaba roto. "
        "Una copia a través de una frontera no diverge de golpe; se atrasa."
    ),
    "prevention": (
        "Dos registros en `vault_criterios`. `CRITERIOS_CON_DUENO`: "
        "criterio, dueño, símbolo por el que se consulta y las constantes "
        "que lo delatan. `FRONTERAS`: cada frontera de lenguaje con su "
        "**zona dueña** (clave de `vault_arch.CONTEXTS`), su **norma** "
        "(código de `vault_norms`) y la **pasarela** —el artefacto derivado— "
        "por la que el criterio debe cruzar. Al otro lado la exención no es "
        "importar al dueño, que no se puede: es leer la pasarela.\n\n"
        "`vault_criterios --check --strict` (puerta 15) falla si aparece "
        "una copia nueva; la baseline **solo encoge** y se salda "
        "importando al dueño o leyendo la pasarela, no ampliándola. El "
        "alcance se declara: un fichero ejecutable de otro lenguaje fuera de "
        "toda zona declarada sale como `frontera_no_declarada`, porque un "
        "sitio donde una copia no se vería vale tanto como una copia.\n\n"
        "El límite se declara antes de que nadie se apoye en él: la "
        "detección es **sintáctica**. Un módulo puede reimplementar un "
        "criterio sin repetir ninguna constante y esta medida no lo verá. "
        "Verde no prueba que no haya copias — prueba que no hay copias de "
        "la forma que sabemos reconocer, que es exactamente lo que da un "
        "linter y es preferible a no mirar."
    ),
    "tools_enforcing": ["vault_criterios"],
    "tools_detecting": ["vault_criterios"],
    "distinguido_de": {
        "CN-05": (
            "AP-57 mide el **criterio** duplicado —el que decide—; CN-05, el "
            "**cuerpo** duplicado —el que se ejecuta—. Un criterio repetido en "
            "dos sitios puede discrepar; un cuerpo repetido hace lo mismo dos "
            "veces, y el segundo arreglo se lleva por delante al primero sin "
            "avisar. AP-57 se salda importando al dueño; CN-05, uniendo los "
            "cuerpos en él."
        ),
        "AP-62": (
            "AP-57 mira el criterio **escrito dos veces**; AP-62 mira el "
            "criterio escrito una sola vez y **leído por la puerta cara**. "
            "El consumidor de AP-62 hace justo lo que AP-57 pide —importar "
            "al dueño en vez de copiar— y aun así paga, porque el dueño "
            "trae el motor detrás. Se saldan al revés: AP-57 juntando el "
            "criterio en un dueño, AP-62 partiendo a ese dueño en catálogo "
            "y motor."
        ),
        "AP-61": (
            "AP-57 es el criterio escrito dos veces sin dueño; AP-61 es una "
            "excepción mal nombrada, que puede darse en un sitio único y sin "
            "copia ninguna. Se cruzan cuando la copia envejece —los doce "
            "sitios corregidos en v40.23 eran las dos cosas a la vez— pero "
            "AP-57 se salda importando al dueño y AP-61 nombrando la "
            "excepción, y un módulo puede quedar limpio de una y no de la otra."
        ),
        "AP-50": (
            "AP-50 es la **decisión duplicada legible**: un vocabulario, "
            "un default de entorno, un regex — dos copias que divergen se "
            "ven al compararlas. AP-57 es su generalización a criterios "
            "enterrados en una condición, donde no hay dato que comparar y "
            "la divergencia solo se nota por el resultado equivocado."
        ),
        "AP-59": (
            "AP-57 habla de un criterio escrito **dos veces** sin dueño; "
            "AP-59, de una **pertenencia afirmada una sola vez** y sin nada "
            "con que contrastarla. No hay copia que comparar: hay una lista "
            "y ninguna medida. Se tocan en el remedio —las dos se cierran "
            "dándole dueño a algo— pero AP-57 se salda importando al dueño "
            "y AP-59 derivando el dato de la forma medida."
        ),
    },
    "introduced_version": "v40.13",
    "revisado_en": "2026-10-09",
}
