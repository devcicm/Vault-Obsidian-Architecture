# AP-77 — Registro con la conservación vencida sin disposición

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de cubrir ISO 15489-1:2016 (2026-11-18). El estándar ya tenía lo que la
norma pide de autenticidad e integridad —no-derogación con `superseded_by:`,
versiones en `.history/`, `responsable` de cada decisión cerrada—, pero no un
calendario de conservación ni una disposición: un registro de 2023 y uno de
ayer se consultaban igual. El calendario vive en `vault_registry`
(`CONSERVACION_POR_CLASE`, `CONSERVACION_POR_SECCION`, `DISPOSICIONES`), junto a
la clase de documento de cada sección, y la norma declara qué hacer cuando
vence.

## Las caras

- **Audit**: `scripts/vault_drift_detect.py::vault_drift_conservacion`, con el
  calendario de su dueño (`vault/kernel/registry.py::conservacion_de`) y la
  aritmética de las normas
  (`vault/kernel/normativa/norms_catalog.py::estado_de_revision`).
- **Tests**: `tests/test_iso_15489_conservacion.py` y `test_ap77_norma.py`.

## Por qué no destruye

Las disposiciones son `conservar`, `revisar` y `archivar`. Destruir un registro
es la disposición final que ISO 15489 deja a la organización, y en este
estándar choca con la no-derogación: lo que una nota sustituida o archivada
dejó escrito sigue siendo la prueba de lo que se decidió. La tool lista; una
persona decide y aplica.

## Por qué no es una puerta

Es una lista de trabajo. Una puerta que fallara por un plazo haría que lo
barato fuera tocar `updatedAt` o poner hoy en `revisado_en` sin releer nada,
que es justo la disposición que la norma pide no fingir.
