# AP-71 — Concepto importante sin página propia

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de la LLM Wiki de Karpathy (fase 3 del plan del 2026-11-16): de sus tres
operaciones —ingesta, consulta y lint— el lint del estándar ya veía enlaces
rotos, huérfanas y contradicciones de dato tipado (AP-05), pero no la cuarta
cosa que el lint de la wiki busca: los conceptos importantes que se mencionan
sin tener página. Hasta aquí, el «qué documentar después» de `vault_audit` se
derivaba de cuántas notas tiene cada carpeta, que dice cuánto hay y no qué
falta.

## Las caras

- **Criterio** (dueño único, AP-57): `vault/kernel/normativa/conceptos.py::conceptos_sin_pagina`,
  con la regla de entidades que la ingesta ya usaba (`vault/kernel/normativa/conceptos.py::extraer_entidades`).
- **Detección**: `scripts/vault_audit.py::_detect_conceptos_sin_pagina` publica
  `conceptsWithoutPage`, y `scripts/vault_audit.py::_acciones_de_conceptos` lleva los
  más citados a `nextActions`.
- **Tests**: `tests/test_karpathy_conceptos.py`.

## Lo que no dice

No dice que el concepto sea importante en un sentido semántico: dice que el
vault lo menciona a menudo. Un umbral declarado y no calibrado
(`UMBRAL_CONCEPTO`) decide cuántas menciones bastan. Tampoco mira la prosa sin
mayúsculas: un concepto escrito siempre en minúsculas no es una entidad para
esta regla, y reconocerlo pediría los embeddings que el estándar no tiene.
