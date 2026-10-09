"""AP-38 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-38",
    "distinguido_de": {
        "AP-39": (
            "Las dos fallan sobre el mismo vocabulario. AP-38 es de orden: se "
            "valida después de escribir, así que el valor malo ya está en disco. "
            "AP-39 es de memoria: el vocabulario es abierto y nadie registra lo "
            "que se aceptó, así que no hay contra que validar. El discriminador "
            "es si existe la lista de referencia."
        ),
    },
    "name": "Vocabulario validado después de escribir, no antes",
    "type": "antipattern",
    "category": "consistency",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Un campo con vocabulario cerrado se acepta tal cual en la escritura y se "
        "comprueba en un audit posterior. El audit no lo ejecuta nadie — en 1.356 "
        "ejecuciones registradas del parque real, `vault_norms` no aparece ni una "
        "vez — así que el vocabulario no gobierna: solo documenta una intención. "
        "Agravante: que varias tools publiquen vocabularios distintos para el mismo "
        "campo (AP-05 aplicado al dato). Un campo canónico se normaliza en el punto "
        "de escritura y rechaza lo que no pueda derivar; los ejes de dominio "
        "legítimos (resultado de un test, fase de un incidente) van a su propio "
        "campo, no compiten por `status`."
    ),
    "signal": (
        "frontmatter.append(f\"status: {status}\") con un vocabulario local; "
        "valores fuera de STATUS_VOCAB en notas escritas por tools del catálogo; "
        "dos tools con listas de estados distintas para el mismo campo."
    ),
    "prevention": (
        "STATUS_SYNONYMS + normalize_status() normalizan en vault_write antes de "
        "emitir. Las tools con eje propio llaman a status_frontmatter_lines(), que "
        "emite `status` canónico y el campo de dominio desde DOMAIN_STATUS_VOCABS. "
        "Lo que arrastraba información y no era estado se conserva en status_note: "
        "no-derogación aplicada al dato."
    ),
    "tools_enforcing": ["vault_write", "vault_norms"],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v39",
}
