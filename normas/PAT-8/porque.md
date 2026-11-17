# PAT-8 — Respuesta compilada en el wiki

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de la LLM Wiki de Karpathy (Parte A del plan de estrés del 2026-11-17). La
vía existía desde la fase 3 (`vault_ingest --desde-pack` y su paso en el
protocolo de sesión), pero solo como comportamiento de una tool: ninguna norma
decía que guardar la respuesta es el patrón, y un agente que consultara el
catálogo no lo encontraba.

## Las caras

- **El patrón**: `scripts/vault_ingest.py::vault_ingest`, la rama del paquete
  (`--desde-pack`), que escribe un solo borrador con las notas del paquete
  citadas y declara `pattern: PAT-8` en su envelope.
- **El paso del protocolo**: `vault/kernel/protocolo_de_sesion.py`, momento
  `recordar`; `vault_preferences --adapters` lo publica en el esquema que lee el
  agente.
- **Tests**: `tests/test_parte_a_normas.py`, `tests/test_karpathy_ingest.py` y
  `test_pat8_norma.py`.
