# AP-66 — El coste crece con lo que no es trabajo

## Por qué existe

La auditoría del 2026-10-15 midió las puertas en 132 s y encontró cinco sitios cuyo coste
crecía con algo distinto de lo que medían. Los cinco se arreglaron antes de declarar la
norma: 0238503, 8e9d639, c44cbea, e9a2f04 y f16fbb3. Por eso la puerta nace en cero y sin
baseline. El texto normativo (señal, prevención y límites) está en `norma.py` y no se
repite aquí.

## Las caras

Cada cara se cita como `ruta::símbolo`. `vault_norms --check-framework` falla si alguna deja
de existir.

- **Criterio:** `scripts/vault_arch.py::costes_que_crecen_en`, sobre un árbol.
- **Aplica y detecta:** `scripts/vault_arch.py::costes_que_crecen`, enganchado en
  `scripts/vault_arch.py::check` bajo `growing_costs`.
- **Heal:** no tiene. Pasar de un proceso por elemento a uno por lote es un rediseño, no una
  reescritura que se pueda automatizar.
- **Tests:** `test_ap66_norma.py`, en este paquete, y `tests/test_ap66_coste_que_crece.py`.
  Los tests que cuentan trabajo de cada arreglo están en `tests/test_baseline.py`,
  `tests/test_grafo_import.py`, `tests/test_arquitectura.py` y
  `tests/test_kernel_huellas_sin_historia.py`.
