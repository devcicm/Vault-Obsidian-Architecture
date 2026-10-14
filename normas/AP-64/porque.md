# AP-64 — Decisión cerrada sin responsable

## Por qué existe

Un ADR aprobado es lo que un agente consulta antes de actuar. Si nadie responde
de su porqué, el agente no distingue una decisión que tomó una persona de una
que otro agente escribió y dio por buena. El texto normativo —señal,
prevención, límites y la regla 7— está en `norma.py` y no se repite aquí.

## Las caras

Cada una se cita como `ruta::símbolo`; `vault_norms --check-framework` falla si
alguna deja de existir.

- **Criterio** (dueño único, lo leen las otras):
  `vault/kernel/contenido.py::falta_de_responsable`, sobre la misma definición
  de ADR que AP-07, `vault/kernel/contenido.py::es_adr`. El régimen del estado
  lo deriva `scripts/vault_registry.py::regimen_de_estado`.
- **Prevención** al escribir: `vault/kernel/contenido.py::meta_adr` propone el
  ADR en `draft` y sin `responsable` de relleno, y el contrato v41 declara el
  campo (`vault/kernel/contrato_nota.py`).
- **Detección**: `scripts/vault_norms.py::vault_norms_scan` y
  `vault/gobernanza/auditoria_runtime.py::auditar_runtime`.
- **Heal**: no tiene. Quién responde de una decisión lo escribe esa persona; un
  programa que lo rellenara pasaría la norma sin nadie detrás.
- **Tests**: `test_ap64_norma.py`, en este paquete, y
  `tests/test_ap64_responsable.py::test_ap64_scan_y_auditoria_marcan_lo_mismo`.

## Por qué es la segunda

Las normas migran por atrición, de la más reciente hacia atrás (deuda #10,
`la_norma_no_es_un_paquete`). AP-65 fue la piloto; AP-64 es la anterior en el
catálogo y la primera que migra con tests que ya vivían fuera del paquete, que
se conservan donde estaban.
