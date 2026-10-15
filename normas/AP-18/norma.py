"""AP-18 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-18",
    "distinguido_de": {
        "AP-17": (
            "AP-17 tiene canónico y sombra: una de las dos manda. AP-18 es "
            "duplicación entre carpetas sin jerarquía declarada —dos copias de "
            "igual rango—, y por eso su reparación empieza por decidir cual es la "
            "canónica, que AP-17 ya tiene decidido."
        ),
        "AP-19": (
            "AP-18 duplica contenido en dos carpetas. AP-19 duplica el índice: "
            "hay un índice en la sombra que compite con el canónico. El "
            "discriminador es si lo duplicado es material o navegación."
        ),
    },
    "name": "Cross-folder content duplication",
    "type": "antipattern",
    "category": "structure",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Mismo contenido byte-idéntico (MD5) en carpetas distintas. "
        "Penalización vault_audit: −3 por par."
    ),
    "signal": "vault_audit reporta crossFolderDuplicates[].",
    "prevention": "PAT-1: una nota canónica, las demás hacen [[wiki-link]]. Usar vault_change_log --action deleted antes de borrar.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v25",
    "revisado_en": "2026-10-09",
}
