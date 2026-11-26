# AP-81 — Saturación de contexto sin presupuesto ni offloading a puntero

## Por qué existe

Cuando una sesión acumula salidas largas de herramientas sin acotarlas ni
externalizarlas a disco, el agente pierde adherencia a las instrucciones
iniciales antes de terminar la tarea (SPEC-06 / OpenDev).

## Las caras

- **Presupuesto y offloading**: `vault/kernel/presupuesto_contexto.py::evaluar_presion_contexto`, `vault/kernel/presupuesto_contexto.py::offload_texto_a_puntero`
- **Presupuesto de recuperación**: `scripts/vault_context_pack.py::vault_context_pack`
- **Tests**: `normas/AP-81/test_ap81_presupuesto_contexto.py`
