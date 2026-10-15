"""AP-51 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-51",
    "distinguido_de": {
        "AP-52": (
            "Las dos son fallos del manejo de error en una tool. AP-51 es la "
            "atribución: la tool devuelve un vacío que culpa al dato de su propio "
            "fallo. AP-52 es la forma: el envelope de error se emite fuera del "
            "contrato de ERROR_CATALOG. Un error puede estar bien atribuido y mal "
            "formado, y al revés."
        ),
        "AP-61": (
            "Son los dos extremos del mismo eje. AP-51 es el handler "
            "**demasiado ancho**: captura de más, se traga el fallo propio y "
            "devuelve un vacío indistinguible de un resultado legítimo. "
            "AP-61 es el handler **demasiado estrecho**: nombra menos de lo "
            "que la llamada lanza, así que no se traga nada — deja pasar. El "
            "discriminador es que pasa después del fallo: con AP-51 la tool "
            "sigue y miente, con AP-61 la tool cae."
        ),
    },
    "name": "La tool culpa al dato de su propio fallo",
    "type": "antipattern",
    "category": "quality",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Una tool falla al leer o al interpretar algo, se traga el fallo y "
        "devuelve un vacio que el llamante no puede distinguir de un "
        "resultado legitimo. El error deja de ser un error y pasa a ser un "
        "**hecho sobre el vault**: el informe que lo agregue dira que N "
        "notas no tienen aliases, y no sera cierto \u2014 es que no se "
        "pudieron leer.\n\n"
        "No es lo mismo *no hay* que *no pude mirar*, y esa es toda la "
        "norma. AP-44 cubre la mitad de arriba \u2014verificar con el "
        "criterio del consumidor y no con el propio\u2014; esta cubre la de "
        "abajo, que es el mecanismo por el que un fallo propio acaba "
        "pareciendo un dato malo. Salio al ejecutar contra un vault ajeno "
        "al estandar (**regla 7**): tres tools declaraban invalidas notas "
        "que Obsidian leia sin problema. Las notas estaban bien; el "
        "criterio que las media, no.\n\n"
        "Lo que la norma **no** prohibe es capturar amplio. Prohibe "
        "capturar amplio y callarse: devolver `ok: false` con el error es "
        "correcto porque el llamante recibe la mala noticia y decide. "
        "Capturar `FileNotFoundError` tampoco infringe: es un criterio, el "
        "autor sabe que tolera y por que. Lo que infringe es `except "
        "Exception: return []`.\n\n"
        "Medida en v40.1: **86 sitios en 37 modulos**. Nace con baseline "
        "por la misma razon que AP-37 \u2014que empezo en 55 y llego a "
        "0\u2014: un guard que falla en 86 sitios se desactiva el primer "
        "dia, y un guard desactivado no protege nada. La baseline solo "
        "puede encoger.\n\n"
        "El propio detector estreno el fallo que persigue. La primera "
        "version midio 101 sitios porque clasificaba `except "
        "yaml.YAMLError` como captura amplia: son `ast.Attribute` y no "
        "`ast.Name`, asi que caian en la rama del `except` desnudo. "
        "Contaba como infraccion justo las capturas mas precisas del "
        "repo. Quince falsos positivos, y el error era el de AP-44 "
        "cometido dentro del guard."
    ),
    "signal": (
        "Un `except Exception` o un `except` desnudo cuya unica salida es "
        "`return []`, `return {}`, `return None`, `pass` o `continue`; un "
        "recuento agregado que no distingue el cero medido del cero por "
        "fallo de lectura; un veredicto sobre una nota emitido por un "
        "camino que ya habia fallado."
    ),
    "prevention": (
        "Capturar la excepcion concreta que se sabe tolerar, y si se "
        "captura amplio, **exponer**: devolver el fallo en el envelope en "
        "vez de un vacio. Cuando el vacio es la respuesta correcta, "
        "distinguirlo del vacio por fallo con un campo aparte "
        "(`unreadable`, `errors`) para que el agregado no los confunda. "
        "`vault_blame_audit --check --strict` mide por AST y no por "
        "texto: un detector que buscara la cadena `except Exception` no "
        "veria la diferencia entre devolver un vacio y devolver un "
        "envelope con `ok: false`, que es toda la distincion que la norma "
        "sostiene."
    ),
    "tools_enforcing": ["vault_blame_audit"],
    # No se lista `vault_norms --audit`: ese audita el **contenido del
    # vault**, y esta norma es sobre el codigo de las tools. Declararlo
    # aqui seria una tool_detecting que no detecta nada, que es la misma
    # afirmacion no falsable que AP-37 persigue.
    "tools_detecting": ["vault_blame_audit"],
    "introduced_version": "v40.1",
    "revisado_en": "2026-10-09",
}
