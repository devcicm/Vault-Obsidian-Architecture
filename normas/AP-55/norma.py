"""AP-55 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-55",
    "name": "El catálogo de normas se certifica a sí mismo",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "`NORM_CATALOG` declara por norma qué tools la hacen cumplir "
        "(`tools_enforcing`) y cuáles la detectan (`tools_detecting`). Los "
        "dos campos se escriben a mano y nada los contrasta contra lo que "
        "las tools hacen: la cobertura publicada es una promesa sin "
        "verificar.\n\n"
        "Lo caro no es la lista, es el guard. `vault_voice.coverage()` "
        "existe para detectar normas mudas y comprueba que una norma tenga "
        "`tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` "
        "y `tools_detecting`**. Verifica el catálogo contra el catálogo, "
        "así que da verde sobre las 47 afirmaciones que ningún módulo "
        "respalda y es estructuralmente incapaz de verlas. Es AP-44 "
        "cometido dentro del guard de AP-43 — la tercera vez que el "
        "criterio de verificación sale del objeto verificado, tras el test "
        "de cruces de v40.8 y el cero de AP-52 medido sobre un subconjunto "
        "en v40.9.\n\n"
        "La forma general: **dos registros canónicos que hablan del mismo "
        "hecho no pueden contradecirse sin que algo falle.** Medido en "
        "v40.10: 54 valores de `tools_*` que mezclaban la tool con su flag "
        "y ningún consumidor podía resolver; AP-22 declarada `critical` "
        "mientras `vault_audit` la penalizaba con 2 puntos por unidad "
        "frente a los 5 de AP-24, que el catálogo llamaba `high`; y 47 "
        "afirmaciones de cobertura sin una línea de código que nombre la "
        "norma. `AP-05` —`critical`— nombra `vault_graph_inspect` como "
        "detector, y esa tool no la menciona en ninguna parte."
    ),
    "signal": (
        "Un valor de `tools_*` que no resuelve contra `mapa_de_grupos()`; "
        "una norma cuya `severity` invierte el orden que "
        "`vault_audit.PENALIZACIONES` aplica dentro de su misma familia; un "
        "módulo declarado enforcer que nunca nombra el código de la norma; "
        "un `distinguido_de` que solo declara una de las dos partes."
    ),
    "prevention": (
        "`vault_norms_coherence --check --strict` cruza el catálogo con el "
        "código y con `PENALIZACIONES`. La traza sin respaldo lleva "
        "baseline que solo puede encoger, y se salda de dos formas "
        "honestas: que el código nombre la norma en el sitio que la "
        "aplica, o que el catálogo deje de afirmar una cobertura que no "
        "tiene. Ampliar la baseline es la tercera y no lo es."
    ),
    "tools_enforcing": ["vault_norms_coherence"],
    "tools_detecting": ["vault_norms_coherence"],
    "distinguido_de": {
        "AP-44": (
            "AP-44 es medir con el propio criterio del objeto medido, en "
            "cualquier tool. AP-55 es su caso en el registro normativo: dos "
            "registros canónicos que afirman cosas distintas sobre el mismo "
            "hecho y nada los cruza. AP-44 se comete al verificar; AP-55 "
            "está en el dato antes de que nadie verifique."
        ),
        "AP-60": (
            "AP-55 mira **con qué criterio** se verifica el catálogo; AP-60, "
            "**a cuántos alcanza** esa verificación. C7 nació de que C5 —una "
            "medida de AP-55 correcta y con criterio ajeno— solo recorría a "
            "las 13 normas que habían declarado algo."
        ),
    },
    "introduced_version": "v40.10",
    "revisado_en": "2026-10-09",
}
