"""PAT-3 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "PAT-3",
    "distinguido_de": {
        "AP-02": (
            "AP-02 es el defecto: la cadena de versiones duplicadas. PAT-3 es el "
            "procedimiento que la resuelve, eligiendo canónico y anotando el "
            "resto sin borrarlo. Saldar AP-02 es aplicar PAT-3."
        ),
    },
    "name": "Duplicate chain resolution",
    "type": "pattern",
    "category": "structure",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Algoritmo estándar para resolver duplicados: identificar canónica (más backlinks, "
        "más contenido, ubicación más apropiada) → change_log --action deleted → "
        "mover a 10_Migrated/ → actualizar wiki-links rotos → verificar con vault_audit."
    ),
    "signal": "vault_audit canonicalShadow reducido después de aplicar.",
    "prevention": "N/A — es el algoritmo de resolución.",
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_audit", "vault_change_log", "vault_write"],
    "introduced_version": "v25",
    "revisado_en": "2026-10-09",
}
