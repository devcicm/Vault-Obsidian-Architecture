"""AP-41 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-41",
    "distinguido_de": {
        "CN-03": (
            "CN-03 mira el valor aislado: pertenece al vocabulario. AP-41 mira la "
            "transición: la máquina de estados está declarada y nadie verifica "
            "que los saltos entre valores sean legales. Todos los valores pueden "
            "ser válidos y la secuencia imposible."
        ),
    },
    "name": "Máquina de estados declarada sin verificar",
    "type": "antipattern",
    "category": "lifecycle",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "El estándar declara STATUS_TRANSITIONS —las transiciones válidas del "
        "ciclo de vida de una nota— y no las recorre nadie: su único consumidor "
        "era su propio test de coherencia. Un estado que no controla su "
        "transición es una etiqueta, no un ciclo de vida: una nota 'archived' "
        "podía volver a 'draft', o saltar de 'planned' a 'verified' sin pasar "
        "por revisión, y ningún guard lo veía. Es la misma forma del fallo "
        "histórico del estándar —declarar sin ejecutar— con la agravante de que "
        "existía un test en verde que verificaba que el grafo estaba bien "
        "dibujado, no que alguien lo recorriera."
    ),
    "signal": (
        "Secuencias de `status` en .history/ que no siguen ninguna arista de "
        "STATUS_TRANSITIONS; notas cuyo estado retrocede sin explicación; "
        "ningún script fuera de los tests importa STATUS_TRANSITIONS."
    ),
    "prevention": (
        "vault_write lee el `status` de la nota en disco antes de sobrescribirla "
        "y rechaza la transición que no está en STATUS_TRANSITIONS, citando los "
        "destinos válidos. Una actualización que no menciona `status` conserva el "
        "estado previo en vez de caer al default 'draft'. Las transiciones ya "
        "ocurridas se reportan desde .history/ con vault_norms --audit: se anotan, "
        "no se reescriben, porque el estado actual es un hecho."
    ),
    "tools_enforcing": ["vault_write"],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v39",
}
