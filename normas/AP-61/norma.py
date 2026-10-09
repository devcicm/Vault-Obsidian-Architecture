"""AP-61 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-61",
    "name": "El guard cae con el dato que vino a medir",
    "type": "antipattern",
    "category": "quality",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Un handler captura la excepción que una librería **declara** y deja "
        "escapar la que esa librería **lanza de verdad**. El `try` parece "
        "contener el fallo y no lo contiene: la excepción sube entera y "
        "tumba la ejecución completa. Lo caro es la asimetría de alcance — "
        "el dato defectuoso es de una nota, la caída es del barrido entero, "
        "así que un solo fichero hostil deja al vault sin medida.\n\n"
        "El caso que le dio nombre: `RecursionError` **no hereda de "
        "`yaml.YAMLError`**. El parser de PyYAML es recursivo y el "
        "frontmatter es dato externo, así que `x: [[[[[…` —doce caracteres "
        "de escribir— desborda la pila dentro de `safe_load`, por encima de "
        "cualquier `except yaml.YAMLError`. `vault_lib.parse_frontmatter` lo "
        "resolvió y lo dejó escrito; los otros **doce sitios** que habían "
        "copiado el mismo `try` no se enteraron de la corrección, y entre "
        "ellos estaba `vault_foreign_check`, que es la tool de la regla 7 y "
        "por tanto la única que corre contra material que este repo no "
        "generó — exactamente donde el dato hostil aparece.\n\n"
        "Es primo de AP-57 y llega por su camino: un criterio copiado "
        "envejece por su lado, y aquí envejeció hacia el lado que deja caer "
        "la tool."
    ),
    "signal": (
        "Un `except` que nombra la excepción base de una librería alrededor "
        "de una llamada que también lanza `RecursionError`, `MemoryError` o "
        "una excepción de otra jerarquía; una tool que muere entera con un "
        "fichero concreto en vez de contarlo como fichero defectuoso."
    ),
    "prevention": (
        "`vault_excepcion_declarada --check --strict` recorre los `try` cuyo "
        "cuerpo contiene una llamada de riesgo declarada en `RIESGOS` y "
        "exige que la excepción que escapa esté nombrada. Se salda "
        "**delegando en el dueño que ya la contuvo** —para el frontmatter, "
        "`vault_lib.parse_frontmatter`— y solo cuando la firma de retorno lo "
        "impide, nombrándola en la tupla y citando al dueño en un "
        "comentario: ampliar la tupla en trece sitios sin dueño es AP-57 "
        "cometido al arreglar AP-61.\n\n"
        "Límite declarado: solo ve la llamada de riesgo escrita **a la "
        "vista** en el cuerpo del `try`. Un `safe_load` detrás de un helper "
        "queda fuera del alcance, que es la forma correcta de escribirlo — "
        "así que este guard mide mejor el código que peor está escrito, y "
        "eso se publica en vez de suponerse cubierto."
    ),
    "tools_enforcing": ["vault_excepcion_declarada"],
    "tools_detecting": ["vault_excepcion_declarada"],
    "distinguido_de": {
        "AP-51": (
            "Son los dos extremos del mismo eje. AP-51 es el handler "
            "**demasiado ancho**: captura `Exception`, se traga el fallo "
            "propio y devuelve un vacío que nadie distingue de un resultado "
            "legítimo. AP-61 es el handler **demasiado estrecho**: nombra "
            "menos de lo que la llamada lanza, así que no se traga nada — "
            "deja pasar. El discriminador es qué pasa después del fallo: "
            "con AP-51 la tool sigue y miente, con AP-61 la tool cae."
        ),
        "AP-57": (
            "AP-57 es el criterio escrito dos veces sin dueño; AP-61 es una "
            "excepción mal nombrada, que puede darse en un sitio único y sin "
            "copia ninguna. Se cruzan cuando la copia envejece —los doce "
            "sitios de v40.23 eran las dos cosas a la vez— pero AP-57 se "
            "salda importando al dueño y AP-61 se salda nombrando la "
            "excepción, y una tool puede quedar limpia de una y no de la otra."
        ),
    },
    "introduced_version": "v40.23",
}
