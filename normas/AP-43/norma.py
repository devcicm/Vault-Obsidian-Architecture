"""AP-43 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-43",
    "distinguido_de": {
        "AP-40": (
            "AP-40 es la contradicción visible: el contrato publicado acepta algo "
            "que la CLI rechaza. AP-43 es la ausencia: la norma existe y el punto "
            "de uso no la menciona ni la aplica. El discriminador es si hay dos "
            "afirmaciones en conflicto o solo una sin refuerzo."
        ),
    },
    "name": "Norma sin refuerzo en el punto de uso",
    "type": "antipattern",
    "category": "governance",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "El catálogo de normas está completo, versionado y con guards, pero el "
        "agente que documenta el vault no lo tiene delante mientras trabaja: se "
        "entera de que una norma existe cuando la incumple —y solo si esa norma "
        "es una de las 14 que previenen, no una de las 33 que se limitan a "
        "detectar en un audit que puede no correrse nunca. El refuerzo llega "
        "tarde, fuera de contexto o no llega. Una norma que el agente no ve en el "
        "momento de escribir no gobierna la escritura: gobierna el post-mortem."
    ),
    "signal": (
        "Normas que ninguna tool declara en tools_enforcing ni tools_detecting "
        "(no se pronuncian nunca); resultados de tool que no llevan bloque "
        "`vault_says`; agentes que repiten el mismo antipatrón entre sesiones."
    ),
    "prevention": (
        "vault_errors.wrap_main —el único punto por el que ya pasa la salida de "
        "todas las tools— añade a cada resultado un bloque `vault_says` derivado "
        "de NORM_CATALOG y del estado real de esa llamada: qué norma acaba de "
        "actuar, cuántas notas cambiaron, qué mirar a continuación. El refuerzo "
        "rota entre las normas que gobiernan esa tool para no degradarse en ruido "
        "fijo. vault_voice --coverage nombra las normas que ninguna tool pronuncia."
    ),
    "tools_enforcing": ["vault_voice", "vault_errors"],
    "tools_detecting": ["vault_voice", "vault_norms"],
    "introduced_version": "v39",
}
