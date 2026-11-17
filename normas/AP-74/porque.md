# AP-74 — Operación sin fila en la bitácora

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de la LLM Wiki de Karpathy (Parte A del plan de estrés del 2026-11-17):
cada ingesta y cada lint dejan una entrada en un log que solo crece. Las filas
`ingested` y `linted` ya existían, pero la fila de una ingesta nombra la sección
y no las notas, así que nada podía decir si una nota ingerida tenía la suya.

## Las caras

- **Prevención** (el enlace): `scripts/vault_ingest.py::vault_ingest` genera el
  id de la pasada y `scripts/vault_ingest.py::_build_note` lo escribe en cada
  nota (`ingest_pass`); la fila lo nombra.
- **Audit**: `scripts/vault_audit.py::_detect_ingestas_sin_bitacora`, en solo
  lectura sobre `00_System/.change-log.json`.
- **Tests**: `tests/test_parte_a_normas.py` y `test_ap74_norma.py`.

## Lo que no dice

No mira las filas `linted`: un lint que no deja fila no produce ninguna nota que
la reclame. Y no repara la bitácora: una fila escrita después del hecho sería una
reconstrucción, no una constancia (SP-01).
