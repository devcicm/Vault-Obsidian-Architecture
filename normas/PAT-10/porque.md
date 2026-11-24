# PAT-10 — Taxonomía de operaciones de lógica de negocio y catálogo oficial de patrones

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Separar lectura y escritura (CQRS) resuelve el transporte y la concurrencia,
pero no describe qué hace la lógica de negocio de un proyecto externo ni con qué
patrones arquitectónicos está construida. A la vez, acoplar el estándar a un
dominio concreto (como un ERP) contaminaría una memoria documental generalista.
Esta norma fija dos acuerdos transversales orientados al consumidor:

1. Clasificar cada feature o flujo detectado en ocho operaciones universales de
   lógica de negocio (`auth`, `rule`, `lifecycle`, `workflow`, `transform`,
   `event`, `integration`, `query`), devolviendo `unclassified` cuando no hay
   evidencia verificable (AP-45).
2. Nombrar todo patrón arquitectónico, de diseño, concurrencia o resiliencia con
   su nombre oficial estándar de la industria desde el catálogo canónico único,
   evitando nombres caseros ad-hoc en el onboarding o en herramientas aisladas.

## Las caras

- **Clasificador canónico de operaciones**:
  `vault/kernel/features_y_flujos.py::clasificar_operaciones_negocio`, llamado
  por `vault/kernel/features_y_flujos.py::detectar_features_y_flujos`.
- **Exposición CQRS de lectura**:
  `scripts/vault_code_query.py::cmd_scan_features`,
  `scripts/vault_pattern_list.py::vault_pattern_catalog` y
  `scripts/vault_pattern_list.py::vault_pattern_detect`.
- **Tests**: `tests/test_detector_features_y_flujos.py`,
  `tests/test_patrones_diseno_detector.py` y `test_pat10_norma.py`.
