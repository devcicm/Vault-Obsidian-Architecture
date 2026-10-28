"""CN-05 — la entrada del catálogo, en su paquete (v41.25).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Las caras están en `porque.md`.
"""

NORMA = {
    "code": "CN-05",
    "distinguido_de": {
        "AP-57": (
            "AP-57 mide el **criterio** duplicado —el que decide—; CN-05, el "
            "**cuerpo** duplicado —el que se ejecuta—. Un criterio repetido en "
            "dos sitios puede discrepar; un cuerpo repetido hace lo mismo dos "
            "veces, y el segundo arreglo se lleva por delante al primero sin "
            "avisar."
        ),
        "CN-04": (
            "CN-04 fija cómo abre una nota; CN-05, quién es el dueño de un "
            "cuerpo de código. Una es convención de escritura y la otra de "
            "estructura del repo: no se solapan ni se contradicen."
        ),
    },
    "name": "One body, one owner — un cuerpo, un dueño",
    "type": "antipattern",
    "category": "convention",
    "severity": "medium",
    "enforcement": "guard",
    "description": (
        "Un cuerpo de código tiene un dueño, y ese dueño es el único sitio "
        "donde se escribe. Medido el 2026-10-28 sobre `scripts/`, `vault/` y "
        "`cli/`: 39 nombres de función definidos en más de un módulo —19 de "
        "ellos `slugify`, con 15 sombras puras que delegaban en el dueño sin "
        "decirlo— y un par de definiciones byte a byte idénticas en "
        "`vault/kernel/proyectos.py`, donde la segunda tapaba a la primera sin "
        "que nada lo dijera. Un cuerpo copiado es una promesa de que las dos "
        "copias se portan igual; esa promesa se rompe sola, sin ruido, en "
        "cuanto una de las dos cambia. Por eso la norma no se conforma con "
        "«no escribas el mismo cuerpo dos veces»: nombra al dueño, y el guard "
        "mide lo que ya está copiado para que la deuda se vea y no se "
        "herede."
    ),
    "signal": (
        "Dos módulos con la misma función —cuerpo idéntico una vez "
        "normalizado, sin el docstring— o dos definiciones del mismo nombre "
        "dentro de un módulo, o una definición que tapa un nombre importado."
    ),
    "prevention": (
        "Buscar el dueño antes de escribir: si el cuerpo existe, se importa; "
        "si no, se escribe en el dueño y se llama desde donde haga falta. "
        "`vault_clones` mide por AST lo que se cuela, y los duplicados que no "
        "se pueden fusionar —porque fusionarlos cruzaría una frontera de "
        "contexto o crearía un módulo para un solo uso— se declaran con su "
        "motivo escrito en una baseline que solo encoge."
    ),
    "tools_enforcing": ["vault_clones"],
    "introduced_version": "v41.25",
    "revisado_en": "2026-10-28",
}
