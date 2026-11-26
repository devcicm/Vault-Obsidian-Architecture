# AP-82 — Recurso adquirido sin Dispose/RAII, lease ni cierre ordenado

## Por qué existe

Es una norma privada (`interno_estandar`) para los desarrolladores del estándar y
el toolkit: todo recurso adquirido debe liberarse de forma determinista (LIFO),
idempotente y sin ocultar la causa raíz de un fallo (SPEC-05 Pilar 5).

## Las caras

- **RAII / Dispose**: `vault/kernel/ciclo_ejecucion.py::GestorDispose`
- **Graceful Shutdown**: `vault/kernel/ciclo_ejecucion.py::instalar_cierre_ordenado`
- **Heartbeat & Lease**: `vault/kernel/ciclo_ejecucion.py::LeaseHeartbeat`
- **Orquestador interno**: `scripts/vault_fix_all.py::fix_all`
- **Tests**: `normas/AP-82/test_ap82_dispose_y_lease.py`
