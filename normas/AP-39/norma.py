"""AP-39 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-39",
    "distinguido_de": {
        "AP-38": (
            "Las dos fallan sobre el mismo vocabulario. AP-38 es de orden: se "
            "valida después de escribir, así que el valor malo ya está en disco. "
            "AP-39 es de memoria: el vocabulario es abierto y nadie registra lo "
            "que se aceptó, así que no hay contra que validar. El discriminador "
            "es si existe la lista de referencia."
        ),
    },
    "name": "Vocabulario abierto sin memoria",
    "type": "antipattern",
    "category": "consistency",
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Un campo con vocabulario abierto (tags) admite términos nuevos sin dejar "
        "constancia de quién los introdujo ni cuándo. Sin registro no hay "
        "continuidad: cada sesión reinventa las palabras de la anterior, y el "
        "vocabulario crece sin converger — 1.180 términos para 6.358 usos, el 45% "
        "usado una sola vez. A diferencia de AP-38, la respuesta correcta NO es "
        "rechazar: un vocabulario abierto que rechaza empuja a omitir el campo, y "
        "entonces lo que se incumple es AP-26. Lo que hay que cerrar es el olvido, "
        "no la entrada."
    ),
    "signal": (
        "Tags que solo difieren en acento, mayúscula, separador o plural conviviendo "
        "en el mismo vault; proporción de términos usados una sola vez que no baja "
        "con el tiempo; el camino de escritura no lee el registro de vocabulario."
    ),
    "prevention": (
        "vault_write llama a vault_tags.apply_vocabulary() antes de emitir: colapsa "
        "contra el registro canónico lo que es demostrablemente la misma palabra "
        "(normalize_tag + singular_tag) y admite el término nuevo tal cual. Una vez "
        "la nota está en disco, record_new_tags() lo anota en la bitácora "
        "append-only 19_Audits/vocabulary/tag-ledger.json con agente, fecha y nota "
        "de origen. Inventar sigue siendo posible; deja de ser silencioso."
    ),
    "tools_enforcing": ["vault_write", "vault_tags"],
    "tools_detecting": ["vault_tags", "vault_norms"],
    "introduced_version": "v39",
    "revisado_en": "2026-10-09",
}
