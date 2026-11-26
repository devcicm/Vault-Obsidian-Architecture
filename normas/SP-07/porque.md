# SP-07 — Compactación adaptativa en 5 umbrales y recordatorios JIT por eventos

## Por qué existe

En sesiones largas (>15–40 turnos) la atención sobre el *system prompt* decae y
el resumen todo-o-nada destruye contexto reciente útil. La escalera 70/80/85/90/99%
más recordatorios JIT breves mantiene la calidad en ambos modos (Harness Nativo y
Standalone CLI/MCP).

## Las caras

- **Escalera 5 umbrales**: `vault/kernel/presupuesto_contexto.py::evaluar_presion_contexto`, `vault/kernel/presupuesto_contexto.py::compactar_observaciones`
- **Triggers JIT**: `vault/kernel/presupuesto_contexto.py::evaluar_triggers_jit`
- **Voz del vault**: `scripts/vault_voice.py::speak`
- **Tests**: `normas/SP-07/test_sp07_compactacion_y_jit.py`
