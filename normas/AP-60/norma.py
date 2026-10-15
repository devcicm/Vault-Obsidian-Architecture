"""AP-60 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-60",
    "name": "El guard cobra por declarar y regala el silencio",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Un guard comprueba una propiedad **iterando sobre quien ya la "
        "declaró**. Quien no declaró nada queda fuera de su alcance, no por "
        "una decisión sino por la forma del bucle. El efecto es un incentivo "
        "invertido: declarar cuesta —obliga a mantener lo declarado, a veces "
        "a editar el otro extremo— y callarse sale gratis y verde.\n\n"
        "Medido en v40.21 sobre C5 de `vault_norms_coherence`: la "
        "comprobación de que dos normas se distinguen recorre "
        "`distinguido_de`, así que solo alcanzaba a **13 normas de 71**. Las "
        "otras 58 no estaban exentas: estaban invisibles. Y declarar una "
        "distinción en AP-59 costó tres ediciones recíprocas y un fallo de "
        "puerta, mientras no declarar ninguna habría salido verde a la "
        "primera.\n\n"
        "Es la misma forma que el repo ya prohíbe en `cobertura_descubierta` "
        "—una norma que declara su hueco no cuenta como deuda nueva, porque "
        "declararse honestamente no puede salir más caro que callarse—, "
        "cometida en el guard que vigila el catálogo donde esa regla está "
        "escrita."
    ),
    "symptoms": (
        "Un guard cuyo bucle empieza por un campo opcional; una medida cuyo "
        "total no puede subir porque el denominador es la lista de quienes "
        "ya hablaron; un envelope que publica cuántos casos revisó y no "
        "cuántos existían."
    ),
    "prevention": (
        "Medir sobre el universo —el catálogo, el registro, el conjunto de "
        "módulos— y no sobre el subconjunto que declaró. Admitir dos salidas "
        "honestas, la declaración y la exención con motivo escrito, y "
        "ninguna tercera: el silencio se cuenta como deuda. La baseline "
        "congela lo que ya estaba y solo encoge; lo que estrena se escribe."
    ),
    "tools_enforcing": ["vault_norms_coherence"],
    "tools_detecting": ["vault_norms_coherence"],
    "distinguido_de": {
        "AP-55": (
            "AP-55 es el catálogo verificándose con el catálogo: el criterio "
            "sale del propio objeto medido. AP-60 no habla del criterio sino "
            "del **alcance**: el criterio puede ser impecable y aun así "
            "aplicarse solo a quien se ofreció voluntario. Un guard puede "
            "medir con criterio ajeno —correcto frente a AP-55— y seguir "
            "recorriendo únicamente a los que declararon."
        ),
        "AP-37": (
            "AP-37 persigue la afirmación **no falsable**: el `ok: true` que "
            "ninguna evidencia podría contradecir. AP-60 persigue la "
            "afirmación falsable pero **parcial**: hay evidencia y se mira, "
            "solo que sobre un subconjunto que se autoselecciona. La primera "
            "no se puede refutar; la segunda se refuta mirando a quien no "
            "aparece en la lista."
        ),
    },
    "introduced_version": "v40.21",
    "revisado_en": "2026-10-09",
}
