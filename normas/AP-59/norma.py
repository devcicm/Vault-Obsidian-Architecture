"""AP-59 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-59",
    "name": "Núcleo declarado sin contraste",
    "type": "antipattern",
    "category": "architecture",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Un sistema declara cuál es su núcleo —la lista de módulos de los "
        "que todo lo demás depende— y **ninguna medida contrasta esa "
        "afirmación** contra la forma real del grafo. La pertenencia al "
        "core deja de ser un hecho y pasa a ser una costumbre: se hereda de "
        "quien escribió la lista, y envejece en la dirección cómoda.\n\n"
        "Lo caro no es equivocarse de lista: es que **todo lo que se apoya "
        "en ella hereda el error en silencio**. Si un módulo está declarado "
        "como núcleo sin serlo, el guard de fronteras lo exime de reglas que "
        "sí debería cumplir y sale verde. Si uno lo es sin estar declarado, "
        "cada cambio suyo propaga hacia arriba sin que nadie lo trate como "
        "un cambio de núcleo. En ambos casos el verde es correcto respecto a "
        "un mapa equivocado.\n\n"
        "Medido en v40.20 sobre este repo, con la lista **bien elegida** —los "
        "cuatro de cabecera eran los correctos y K1 ya estaba verde—: aun "
        "así, **tres de quince módulos del kernel no se comportan como "
        "núcleo**. `vault_log_error` con fan-in 0, declarado núcleo y sin un "
        "solo consumidor; `vault_io` con fan-out 11 y 30 commits; "
        "`vault_errors` con 14, sobre una mediana de dominio de 9. Ninguno "
        "estaba roto. Ninguno se había visto, porque nadie miraba.\n\n"
        "La norma no exige que el núcleo sea perfecto: exige que su "
        "pertenencia sea **derivable y contrastada**, y que la distancia "
        "entre lo declarado y lo medido se publique en vez de suponerse cero."
    ),
    "signal": (
        "La lista del núcleo se edita a mano y ninguna puerta la lee; un "
        "módulo declarado kernel sin consumidores; un módulo de dominio con "
        "fan-in por encima del escalón de la distribución; el churn del "
        "núcleo por encima de la mediana de lo que sostiene."
    ),
    "prevention": (
        "`vault_kernel --check --strict` (puerta 18) mide tres invariantes. "
        "**K1** —el núcleo no depende del dominio— no se reimplementa: se "
        "delega en `vault_arch.dependencias_del_kernel()`, porque una tool "
        "que mide su propia pureza con su propio criterio es AP-44 cometido "
        "en el sitio que existe para detectarlo. **K2** —fan-in alto, "
        "fan-out bajo— sale del dueño único del grafo de imports "
        "(`vault_grafo_import`), no de un parser propio. **K3** —estabilidad— "
        "del churn de git, y sin historia disponible emite `desconocido` y "
        "nunca `0`: un cero fabricado saldría verde por no haber mirado "
        "(AP-51). Desde v41.3 el churn cuenta **commits que cambian el "
        "comportamiento** —funciones, clases, nombres—, leídos con `ast`; "
        "un commit que solo añade entradas a una tabla, o reescribe un "
        "docstring o un comentario, no mueve al módulo para quien lo "
        "importa. Núcleo y dominio se miden con la misma vara, y el churn "
        "bruto se publica al lado (`raw_churn`) sin decidir nada.\n\n"
        "Los umbrales **se derivan del escalón** de la distribución —la "
        "mayor caída relativa— y se publican en el envelope con su ratio en "
        "cada ejecución. Escribirlos a mano sería AP-47 en la tool que "
        "persigue los números a mano; por eso la baseline congela la "
        "**pertenencia** (qué módulo incumple qué invariante) y no el "
        "umbral, que puede oscilar al crecer el repo.\n\n"
        "Dos límites, dichos antes de que nadie se apoye en el verde. "
        "Primero: mide el grafo **estático** de imports y hereda sus "
        "cegueras (`importlib`, un import por cadena, el acoplamiento por "
        "fichero o por variable global). Segundo: mide **forma, no "
        "propósito**. Un módulo puede tener fan-in altísimo sin ser núcleo "
        "de nada, solo un cajón de utilidades que todo el mundo toca. Verde "
        "significa que la lista declarada no contradice a la forma medida."
    ),
    "tools_enforcing": ["vault_kernel"],
    # `vault_arch` NO se lista aquí aunque mida K1: la delegación va en un
    # solo sentido. `dependencias_del_kernel()` existía antes que la norma y
    # no la nombra, así que declararla detectora sería una cobertura que
    # nadie puede seguir hasta el código — el AP-55 que este catálogo mide.
    "tools_detecting": ["vault_kernel"],
    "distinguido_de": {
        "AP-62": (
            "AP-59 mira la **lista del núcleo** y pregunta si la forma "
            "medida la sostiene. AP-62 mira las **aristas de fuera del "
            "núcleo** y pregunta qué se paga al cruzarlas. Se tocan en la "
            "tentación opuesta: quien quiera bajar la cifra de AP-62 "
            "moviendo el productor al núcleo sin darle forma de hoja se "
            "encuentra con AP-59, y por eso el remedio es partirlo, no "
            "reclasificarlo."
        ),
        "AP-57": (
            "AP-57 habla de un **criterio** escrito dos veces sin dueño. "
            "AP-59 habla de una **pertenencia afirmada y no contrastada**: "
            "no hay copia ninguna, hay una sola lista y nada con qué "
            "compararla. Se tocan en el remedio —los dos se cierran dándole "
            "dueño a algo— pero AP-57 se salda importando al dueño y AP-59 "
            "derivando el dato de la forma medida."
        ),
        "AP-58": (
            "AP-58 mira la **dirección** de las dependencias: quién importa "
            "a quién y si eso vuelve. AP-59 mira **quién está declarado como "
            "fondo de esa pila**. Un repo puede tener cero ciclos y un "
            "núcleo mal declarado, y un núcleo perfecto lleno de ciclos."
        ),
        "AP-47": (
            "AP-47 es la cifra escrita a mano en la documentación. AP-59 es "
            "su versión estructural: la **lista** escrita a mano en el "
            "código. Por eso el remedio comparte disciplina —derivar en vez "
            "de escribir— y por eso los umbrales de esta tool no pueden ser "
            "literales sin cometer AP-47 dentro de AP-59."
        ),
    },
    "introduced_version": "v40.20",
    "revisado_en": "2026-10-09",
}
