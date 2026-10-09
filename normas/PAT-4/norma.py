"""PAT-4 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "PAT-4",
    "distinguido_de": {
        "SP-03": (
            "PAT-4 ordena la auditoría en fases para que un fallo no invalide "
            "todo el recorrido. SP-03 exige el snapshot delta antes de una "
            "operación masiva, para poder decir después que cambio. Uno "
            "estructura el trabajo; el otro conserva la evidencia de lo que hizo."
        ),
    },
    "name": "Phased audit execution",
    "type": "pattern",
    "category": "process",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Las auditorías masivas se ejecutan en 4 fases atómicas: "
        "1-Snapshot (vault_drift_detect --mode snapshot), 2-Detección (vault_audit), "
        "3-Resolución (vault_write, vault_change_log), 4-Verificación (vault_drift_detect --mode report)."
    ),
    "signal": "0 regresiones entre snapshot y estado final.",
    "prevention": "N/A — es el protocolo de auditoría.",
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_drift_detect", "vault_audit", "vault_write", "vault_change_log"],
    "introduced_version": "v25",
}
