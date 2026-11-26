"""AP-83 — Mutación en lote u orquestación sin DAG acíclico, Saga/pre-SHA ni checkpoint (SPEC-05).

Norma privada (`audiencia: "interno_estandar"`): protege los pipelines y lotes
internos del toolkit contra estados parciales corruptos y ciclos implícitos.
Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "AP-83",
    "audiencia": "interno_estandar",
    "distinguido_de": {
        "AP-82": (
            "AP-82 gobierna la liberación determinista de recursos (Dispose/RAII, "
            "leases y Graceful Shutdown). AP-83 gobierna la integridad de las "
            "orquestaciones y lotes multi-paso: dependencias explícitas en DAG "
            "acíclico (`TopologicalSorter`), compensación Saga por pre-SHA Git y "
            "checkpoints JSONL con replay idempotente."
        ),
    },
    "name": "Orquestación o lote sin DAG acíclico, compensación Saga ni checkpoint",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Ejecutar pipelines de múltiples pasos con un orden lineal implícito "
        "o aplicar lotes destructivos sin punto de compensación ni checkpoints "
        "deja el repositorio o el vault en estados intermedios inconsistentes "
        "tras un fallo parcial. Los pipelines internos del estándar declaran "
        "su DAG explícito validado con `graphlib.TopologicalSorter` "
        "(`vault_fix_all.DEPENDENCIAS_PASOS`) y las primitivas de lote usan "
        "`SagaPreSha` y `CheckpointLog` en `00_System/` (AP-36)."
    ),
    "signal": (
        "Un pipeline del toolkit omite validación topológica de dependencias "
        "o un lote compuesto carece de compensación `SagaPreSha` o "
        "`CheckpointLog` para replay idempotente."
    ),
    "prevention": (
        "Validar el orden de pasos mediante `vault_fix_all.orden_topologico_pasos` "
        "(`TopologicalSorter`) y respaldar lotes críticos con "
        "`vault.kernel.ciclo_ejecucion.SagaPreSha` y `CheckpointLog`."
    ),
    "tools_enforcing": ["vault_fix_all"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-26",
}
