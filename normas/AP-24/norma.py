"""AP-24 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-24",
    "name": "Bracket imbalance — corchetes sin pareja, anidados o invertidos",
    "type": "antipattern",
    "category": "linking",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Wiki-links malformados por desbalance de corchetes. Tres variantes: "
        "(1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), "
        "(3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link "
        "se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad "
        "y produce falsos negativos en vault_audit (brokenLinks)."
    ),
    "signal": (
        "vault_write content_gate detecta balance desigual en línea y rechaza la escritura. "
        "vault_audit penaliza con -5 por nota afectada. vault_fix_brackets intenta auto-fix "
        "(eliminación de corchetes extra o inyección de cierre)."
    ),
    "prevention": (
        "Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con "
        "vault_fix_brackets --apply antes de commit. El content_gate de vault_write "
        "rechaza contenido con bracket imbalance."
    ),
    "tools_enforcing": ["vault_write", "vault_fix_brackets"],
    "tools_detecting": ["vault_audit", "vault_fix_brackets"],
    "distinguido_de": {
        "AP-22": (
            "AP-24 es el desbalance de corchetes: hay un destino escrito y el "
            "desbalance lo vuelve inalcanzable. AP-22 es el link vacío `[[]]`, "
            "sin destino que recuperar. AP-24 pesa más en el healthIndex (5/unidad "
            "frente a 2) precisamente por esa diferencia."
        )
    },
    "introduced_version": "v34.2",
    "revisado_en": "2026-10-09",
}
