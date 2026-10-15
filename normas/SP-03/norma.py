"""SP-03 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "SP-03",
    "distinguido_de": {
        "PAT-4": (
            "PAT-4 ordena la auditoría en fases para que un fallo no invalide "
            "todo el recorrido. SP-03 exige el snapshot delta antes de una "
            "operación masiva, para poder decir después que cambio. Uno "
            "estructura el trabajo; el otro conserva la evidencia de lo que hizo."
        ),
        "SP-01": (
            "SP-01 protege el borrado concreto: no se elimina sin `change_log` "
            "previo. SP-03 protege la tanda: no se opera en masa sin snapshot. El "
            "discriminador es el alcance —una nota frente a una operación— y por "
            "eso un borrado masivo exige los dos."
        ),
    },
    "name": "Session snapshot pattern — delta antes de operaciones masivas",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Antes de cualquier operación masiva (migración, rename en lote, vault_tags --rename "
        "múltiple, delete en lote), capturar snapshot con vault_delta --snapshot. "
        "Permite detectar regresiones y calcular impacto real de la operación."
    ),
    "signal": "Operación masiva sin snapshot previo → no hay baseline para detectar regresiones.",
    "prevention": (
        "PAT-4 (phased audit): snapshot → operación → vault_audit() → comparar score. "
        "vault_delta --snapshot antes de cada sesión con cambios masivos."
    ),
    "tools_enforcing": [],
    # `vault_backup` copia el vault entero; el snapshot que SP-03 pide —y que
    # su propia descripción nombra— lo toma `vault_delta --snapshot`, que es
    # además quien luego calcula el delta contra él.
    "tools_detecting": ["vault_delta"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
