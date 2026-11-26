# AP-83 — Orquestación o lote sin DAG acíclico, compensación Saga ni checkpoint

## Por qué existe

Es una norma privada (`interno_estandar`) para garantizar que los pipelines y
lotes internos del toolkit operen con DAG explícito sin ciclos, compensación
determinista por pre-SHA Git y replay idempotente mediante checkpoints JSONL
(SPEC-05 Etapa 2).

## Las caras

- **DAG topológico**: `scripts/vault_fix_all.py::orden_topologico_pasos`
- **Compensación Saga pre-SHA**: `vault/kernel/ciclo_ejecucion.py::SagaPreSha`
- **Checkpoints y replay**: `vault/kernel/ciclo_ejecucion.py::CheckpointLog`
- **Tests**: `normas/AP-83/test_ap83_dag_saga_checkpoint.py`
