# AP-76 — Nota viva con la revisión vencida

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace del vídeo de Torti Code sobre documentación útil (Parte A del plan de
estrés del 2026-11-17). `vault_drift_detect --mode antiguedad` ya listaba las
notas vencidas desde la fase 4, con la misma aritmética que gestiona la revisión
de las propias normas; faltaba la norma que lo declarase y que el agente la
pudiera consultar.

## Las caras

- **Audit**: `scripts/vault_drift_detect.py::vault_drift_antiguedad`, con el
  criterio de su dueño
  (`vault/kernel/normativa/norms_catalog.py::estado_de_revision`).
- **Tests**: `tests/test_parte_a_normas.py`, `tests/test_torti_documentacion.py`
  y `test_ap76_norma.py`.

## Por qué no es una puerta

Es una lista de trabajo. Una puerta que fallara por una fecha haría que la forma
más barata de pasarla fuera escribir hoy en `revisado_en` sin releer nada, que es
exactamente la revisión que la norma pide no fingir.
