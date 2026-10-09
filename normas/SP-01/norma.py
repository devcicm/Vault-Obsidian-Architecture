"""SP-01 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "SP-01",
    "distinguido_de": {
        "SP-03": (
            "SP-01 protege el borrado concreto: no se elimina sin `change_log` "
            "previo. SP-03 protege la tanda: no se opera en masa sin snapshot. El "
            "discriminador es el alcance —una nota frente a una operación— y por "
            "eso un borrado masivo exige los dos."
        ),
    },
    "name": "Delete protocol — change_log obligatorio antes de eliminar",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "critical",
    "enforcement": "audit",
    "description": (
        "Antes de eliminar cualquier nota del vault, el agente DEBE llamar: "
        "vault_change_log --action deleted --path <nota> --reason <motivo>. "
        "Sin este registro, la nota desaparece sin rastro auditado."
    ),
    "signal": "Nota eliminada que no aparece en 00_System/.change-log.json con action: deleted.",
    "prevention": (
        "Regla de gobernanza: verificar en .change-log.json antes de delete. "
        "Si no hay entrada → llamar vault_change_log primero, luego eliminar."
    ),
    "tools_enforcing": ["vault_change_log"],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v30",
}
