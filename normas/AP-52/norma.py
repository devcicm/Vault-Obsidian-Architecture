"""AP-52 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-52",
    "cobertura_parcial": (
        "Detectada en su parte decidible: literales, `var[\"k\"] = …` y "
        "`var.update(…)` con un dict literal o una variable asignada una sola vez "
        "a uno (`vault_error_contract._literales_unicos`, v41.10). Lo que no se "
        "sigue —y no se adivina—: el valor que llega por una llamada o por una "
        "variable reasignada según el camino. Medido el 2026-10-17: 0 sitios."
    ),
    "distinguido_de": {
        "AP-51": (
            "Las dos son fallos del manejo de error en una tool. AP-51 es la "
            "atribución: la tool devuelve un vacío que culpa al dato de su propio "
            "fallo. AP-52 es la forma: el envelope de error se emite fuera del "
            "contrato de ERROR_CATALOG. Un error puede estar bien atribuido y mal "
            "formado, y al revés."
        ),
    },
    "name": "El error se emite fuera del contrato del catalogo",
    "type": "antipattern",
    "category": "quality",
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Una tool falla, lo dice, y lo dice mal: devuelve `{\"ok\": false, "
        "\"error\": \"...\"}` escrito a mano en vez de pasar por "
        "`vault_errors.emit_error`. La frase es correcta; el contrato, no. "
        "El envelope del catalogo trae `error_code`, `category`, "
        "`severity`, `recovery` y `timestamp`; el escrito a mano no trae "
        "ninguno.\n\n"
        "Importa porque el consumidor no lee la frase: **decide por el "
        "codigo**. El servidor MCP y `cli/` deciden si reintentar, abortar "
        "o pedir permiso mirando `error_code` y `recovery.action`. Sin "
        "ellos, un fallo con recuperacion conocida llega como un fallo "
        "opaco, y la unica salida del agente que lo recibe es adivinar.\n\n"
        "Es AP-05 aplicada al **contrato de error** \u2014hay un registro "
        "que declara como se nombra y se recupera cada fallo, y 158 sitios "
        "que lo deciden por su cuenta\u2014 y es AP-51 vista desde el otro "
        "lado: alli el fallo se disfrazaba de dato, aqui llega como fallo "
        "pero desnudo de todo lo que lo hace accionable.\n\n"
        "Salio de la caracterizacion maliciosa: invocar las 94 tools de "
        "forma malformada y mirar **como** fallan, no si fallan. El grueso "
        "estaba limpio \u2014las 45 tools con `required_args` rechazan la "
        "invocacion vacia por argparse, y las 92 tools Python rechazan un "
        "flag desconocido\u2014 y el hallazgo estaba en la forma del "
        "envelope, no en su ausencia.\n\n"
        "Medida en v40.2: **158 sitios en 58 modulos**. Nace con baseline "
        "por la misma razon que AP-37 y AP-51: un guard que falla en 158 "
        "sitios se desactiva el primer dia. La baseline solo puede "
        "encoger.\n\n"
        "El guard mide **forma y no flujo**: un dict con `ok: False` y "
        "pinta de envelope que no lleva `error_code`. No sigue el valor "
        "hasta stdout, asi que cuenta tambien envelopes internos que nunca "
        "se imprimen. Eso se declara en vez de esconderse: un guard que "
        "promete una precision que no tiene es la clase de afirmacion no "
        "falsable que AP-37 persigue."
    ),
    "signal": (
        "Un literal `{\"ok\": False, \"error\": ...}` en el camino de "
        "salida de una tool; un envelope de fallo sin `error_code`; un "
        "consumidor que tiene que leer `message` con un regex para saber "
        "que paso."
    ),
    "prevention": (
        "Emitir por `emit_error(tool, CODIGO, mensaje)` y, si el codigo no "
        "existe, anadirlo a `ERROR_CATALOG` \u2014 que es donde vive la "
        "decision de como se recupera ese fallo. Anadir el codigo cuesta "
        "una linea; no anadirlo traslada el coste a cada consumidor, para "
        "siempre. `vault_error_contract --check --strict` mide por AST."
    ),
    "tools_enforcing": ["vault_error_contract"],
    # Como en AP-51, no se lista `vault_norms --audit`: audita el
    # contenido del vault, y esta norma es sobre el codigo de las tools.
    "tools_detecting": ["vault_error_contract"],
    "introduced_version": "v40.2",
    "revisado_en": "2026-10-17",
}
