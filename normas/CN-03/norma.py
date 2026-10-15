"""CN-03 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "CN-03",
    "distinguido_de": {
        "AP-29": (
            "CN-03 exige que el valor de `status` esté en el vocabulario "
            "canónico; AP-29 exige que el campo exista. El discriminador es "
            "presencia frente a valor: una nota sin `status` es AP-29 y no puede "
            "ser CN-03."
        ),
        "AP-41": (
            "CN-03 mira el valor aislado: pertenece al vocabulario. AP-41 mira la "
            "transición: la máquina de estados está declarada y nadie verifica "
            "que los saltos entre valores sean legales. Todos los valores pueden "
            "ser válidos y la secuencia imposible."
        ),
    },
    "name": "Standard status vocabulary — vocabulario canónico de meta.status",
    "type": "antipattern",
    "category": "convention",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "El campo meta.status (o status en frontmatter) debe usar solo valores de "
        "vault_norms.STATUS_VOCAB (fuente única, v38 — unifica el vocabulario CN-03 "
        "original con el ciclo de vida del spec §status): planned | draft | in-progress | "
        "reviewed | approved | implemented | verified | deprecated | obsolete | archived | "
        "stub | template. Valores fuera del vocabulario rompen filtros de vault_list y vault_audit."
    ),
    "signal": "vault_list filtra por status y retorna 0 cuando el valor es no-estándar.",
    "prevention": "Usar solo valores de STATUS_VOCAB. vault_norms --audit los valida (CN-03).",
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
