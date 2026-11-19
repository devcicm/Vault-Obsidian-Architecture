# AP-78 — Decisión de IA de impacto alto sin evaluación por afectado

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de cubrir los huecos ISO del registro (`odd/tasks/iso-coverage.md`, T2). La
entrada ISO-42005 de `ISO_COVERAGE` declaraba el hueco: «Registra a quién afecta;
la probabilidad, la severidad por afectado y la mitigación de la evaluación
completa no se registran.» AP-65 lo decía también en sus límites. El registro ya
tenía dónde escribirlo —las escalas de probabilidad e impacto de
`vault_risk_save`— y faltaba que la decisión las usara y que algo avisara cuando
no lo hace.

## Las caras

- **Escritura**: `scripts/vault_ai_decision.py::evaluacion_por_afectado` valida
  cada entrada de `--assessment` antes de escribir; la nota lleva la tabla en
  «Evaluacion de Impacto» y `evaluacion_por_afectado` en el frontmatter. Una
  decisión que no usa la opción se escribe byte a byte como antes.
- **Audit**: `scripts/vault_audit.py::_detect_impacto_sin_evaluacion_por_afectado`,
  publicado en `aiDecisionsWithoutPartyAssessment`.
- **Tests**: `tests/test_iso_42005_impacto_ia.py` y `test_ap78_norma.py`.

## Por qué no es una puerta

Un registro incompleto vale más que ninguno, el mismo criterio que AP-65: rechazar
la decisión por no traer la evaluación completa haría que lo barato fuese no
registrarla. Lo que sí se rechaza es una evaluación mal formada, porque eso no es
un registro incompleto sino uno falso.

## Por qué una norma nueva y no AP-65 ampliada

Endurecer AP-65 para exigir la evaluación por afectado habría cambiado su
veredicto sobre decisiones que hoy la cumplen, sin que nadie las tocara. Son dos
preguntas distintas y la segunda solo se puede contestar después de la primera:
por eso AP-78 no cuenta las decisiones que AP-65 ya marca.
