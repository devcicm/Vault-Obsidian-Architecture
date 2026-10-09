"""AP-58 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-58",
    "name": "Ciclo esquivado con un import diferido",
    "type": "antipattern",
    "category": "architecture",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Dos módulos se necesitan mutuamente, y en vez de invertir la "
        "dependencia se mete uno de los `import` dentro del cuerpo de una "
        "función. Python deja de quejarse, el ciclo sigue ahí y **deja de "
        "verse**: cualquier medida que mire los imports de nivel de módulo "
        "dirá cero ciclos con toda honestidad.\n\n"
        "Aplicado una vez es una excepción razonable. Aplicado muchas es la "
        "arquitectura, tomada sin decidirla. Medido en v40.17 sobre este "
        "repo: **92 imports diferidos en 40 módulos**, de los cuales 30 "
        "esquivan un ciclo, y contándolos aparece un componente "
        "fuertemente conexo de **14 módulos** que contiene el núcleo "
        "entero. Ese componente es el que hacía que `vault_errors_trace` "
        "—un escritor de trazas de bajo nivel— importase `vault_io` "
        "entero, y el que obliga a `cli/runner.py` a aislar cada tool en "
        "un subproceso para que dos raíces no se contaminen.\n\n"
        "El daño no es el arranque: es que la dirección de la dependencia "
        "deja de ser una decisión revisable. Un ciclo escondido no se "
        "discute en revisión porque no aparece en ninguna medida."
    ),
    "signal": (
        "Un `import` de otro módulo del toolkit escrito dentro de una "
        "función, cuyo destino puede volver al origen siguiendo el grafo "
        "completo de imports."
    ),
    "prevention": (
        "`vault_ciclos --check --strict` (puerta 17) calcula los "
        "componentes fuertemente conexos **contando las aristas "
        "diferidas**, que es la única forma de que la pregunta se pueda "
        "formular. La baseline **solo encoge** y se salda invirtiendo la "
        "dependencia —el módulo de bajo nivel deja de pedirle el módulo "
        "entero al de alto y se le pasa lo que necesita—, no subiendo el "
        "import ni ampliando la baseline.\n\n"
        "Dos límites, dichos antes de que nadie se apoye en el verde. "
        "Primero: solo entran en la deuda los diferidos que **esquivan un "
        "ciclo** (30 de 92); los otros 62 se difieren por coste de "
        "arranque o por dependencia opcional y se publican como "
        "`deferred_benign` sin congelarse, porque una baseline llena de "
        "ruido es una baseline que nadie revisa. Segundo: la medida es del "
        "grafo **estático** de módulos. No ve `importlib`, ni un import "
        "construido con una cadena, ni el acoplamiento que pasa por el "
        "sistema de ficheros o por una variable global compartida."
    ),
    "tools_enforcing": ["vault_ciclos"],
    "tools_detecting": ["vault_ciclos"],
    "distinguido_de": {
        "AP-62": (
            "AP-58 mide una dependencia que **vuelve**: el ciclo. AP-62 "
            "mide una que no vuelve nunca y aun así cuesta, porque el "
            "importador solo quería un dato y se lleva el fan-out entero. "
            "Un repo sin un solo ciclo puede estar lleno de arrastre, y el "
            "remedio de AP-62 —partir el productor— es además una de las "
            "formas de romper un ciclo, que es donde se tocan."
        ),
        "AP-49": (
            "AP-49 mira el **vínculo congelado al importar**: un valor que "
            "se copia en tiempo de import y ya no responde a un reanclaje. "
            "AP-58 mira la **dirección** de la dependencia, no su momento. "
            "Se tocan porque el ciclo del núcleo es lo que obliga a "
            "congelar vínculos, pero un módulo puede tener ciclos sin "
            "vínculos congelados y al revés."
        ),
        "AP-54": (
            "AP-54 habla de cruces de frontera entre contextos acotados, "
            "que pueden ser perfectamente acíclicos. AP-58 habla del ciclo "
            "aunque ocurra dentro de un solo contexto — y el componente de "
            "14 módulos vive casi entero dentro del kernel."
        ),
        "AP-59": (
            "AP-58 mira la **dirección** de las dependencias: quién importa "
            "a quién y si eso vuelve. AP-59 mira **quién está declarado como "
            "fondo de esa pila**. Un repo puede tener cero ciclos y un núcleo "
            "mal declarado, y un núcleo impecable lleno de ciclos."
        ),
    },
    "introduced_version": "v40.17",
}
