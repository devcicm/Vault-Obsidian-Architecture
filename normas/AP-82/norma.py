"""AP-82 — Recurso adquirido sin Dispose/RAII, Lease ni Graceful Shutdown (SPEC-05 Pilar 5).

Norma privada (`audiencia: "interno_estandar"`): gobierna los procesos internos
del toolkit para eliminar fugas de handles, locks huérfanos y subprocesos zombis.
Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "AP-82",
    "audiencia": "interno_estandar",
    "distinguido_de": {
        "AP-83": (
            "AP-82 gobierna el ciclo de vida determinista de recursos "
            "(patrón Dispose/RAII en orden LIFO, idempotencia de cierre, "
            "leases con heartbeat y Graceful Shutdown ante SIGTERM/SIGINT). "
            "AP-83 gobierna la durabilidad e integridad transaccional de "
            "lotes multi-paso (DAG acíclico, compensación Saga por pre-SHA y "
            "checkpoints JSONL con replay idempotente)."
        ),
    },
    "name": "Recurso adquirido sin Dispose/RAII, lease ni cierre ordenado",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Adquirir recursos escasos (archivos, locks, timers, subprocesos o "
        "temporales) sin un dueño de liberación determinista en orden LIFO e "
        "idempotente produce fugas de handles, bloqueos huérfanos y cierres "
        "sucios ante excepciones o señales `SIGTERM`/`SIGINT`. En los procesos "
        "internos del toolkit, toda composición de recursos usa `GestorDispose` "
        "(o `with`/`ExitStack`), leases renovables (`LeaseHeartbeat`) y "
        "`instalar_cierre_ordenado` sin ocultar la excepción original (AP-51)."
    ),
    "signal": (
        "Un proceso del toolkit adquiere recursos múltiples sin `GestorDispose`/"
        "`ExitStack`, falla al llamar `dispose()` dos veces, oculta errores de "
        "limpieza o mantiene locks sin expiración."
    ),
    "prevention": (
        "Envolver recursos en `vault.kernel.ciclo_ejecucion.GestorDispose`, "
        "renovar concesiones con `LeaseHeartbeat` y registrar cierre ordenado "
        "con `instalar_cierre_ordenado`."
    ),
    "tools_enforcing": ["vault_fix_all"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-26",
}
