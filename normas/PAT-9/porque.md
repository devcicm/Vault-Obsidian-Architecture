# PAT-9 — Esquema del agente generado

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de la LLM Wiki de Karpathy (la capa de esquema fija carpetas, nombres y
flujos) y del vídeo de Torti Code (AGENTS.md corto que dice dónde viven las
decisiones), en la Parte A del plan de estrés del 2026-11-17. El adaptador ya se
generaba con el mapa, CN-01, el protocolo y las decisiones, y recortaba las
preferencias para caber en 120 líneas; pero si la parte derivada sola crecía,
escribía igualmente un fichero por encima del presupuesto que anunciaba.

## Las caras

- **El patrón y su guard de presupuesto**:
  `scripts/vault_preferences.py::vault_preferences_adapters`, que comprueba
  todos los adaptadores antes de escribir ninguno; el cuerpo lo compone
  `scripts/vault_preferences.py::_cuerpo_adapter`.
- **Tests**: `tests/test_parte_a_normas.py`, `tests/test_torti_documentacion.py`
  y `test_pat9_norma.py`.
