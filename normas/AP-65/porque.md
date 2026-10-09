# AP-65 — Decisión de IA de impacto alto sin evaluación de impacto

## Por qué existe

ISO/IEC 42001 pide registrar qué decidió un sistema de IA y por qué; ISO/IEC
42005 añade a quién afecta. `vault_ai_decision` registraba lo primero y no tenía
dónde escribir lo segundo: una decisión `critical` quedaba con su porqué y sin
el coste que reparte. El texto normativo —señal, prevención, límites y la regla
7— está en `norma.py` y no se repite aquí.

## Las caras

Cada una se cita como `ruta::símbolo`; `vault_norms --check-framework` falla si
alguna deja de existir.

- **Criterio** (dueño único, lo leen las otras tres):
  `vault/kernel/contenido.py::falta_de_evaluacion_de_impacto`, con la escala en
  `vault/kernel/contenido.py::niveles_de_impacto_exigidos`.
- **Prevención** al escribir: `scripts/vault_ai_decision.py::estado_de_evaluacion`
  declara `impact_assessment` y avisa en `hint`; no rechaza la nota.
- **Detección**: `scripts/vault_norms.py::vault_norms_scan` y
  `vault/gobernanza/auditoria_runtime.py::auditar_runtime`.
- **Heal**: no tiene. Saber a quién afecta una decisión es justo lo que un
  programa no puede escribir por nadie.
- **Tests**: `test_ap65_norma.py`, en este paquete, y
  `tests/test_iso42005_impacto.py::test_ap65_scan_y_auditoria_marcan_lo_mismo`.

## Por qué es la piloto

Era la última norma del catálogo (`introduced_version` v41.3) cuando se movió el
paquete (deuda #10, `la_norma_no_es_un_paquete`): las normas migran por
atrición, empezando por las que se escriben ahora, y no 71 de golpe.
