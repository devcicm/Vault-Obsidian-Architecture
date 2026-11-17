# AP-75 — Decisión cerrada reescrita

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace del vídeo de Torti Code sobre documentación útil (Parte A del plan de
estrés del 2026-11-17): un ADR aprobado se sustituye, no se reescribe. La valla
ya existía como opción del vault (`sustitucion` en `reglas.json`, fase 4), pero
no tenía norma que la nombrara, y un vault que no optaba no tenía nada que le
avisara de la decisión reescrita.

## Las caras

- **Guard** (opt-in): `scripts/vault_io.py::_decision_cerrada_reescrita`,
  dentro del dueño de la escritura; el modo lo decide
  `vault/kernel/registry.py::cambio_de_cuerpo_exige_nota_nueva`.
- **Audit** (siempre): `scripts/vault_audit.py::_detect_decisiones_reescritas`,
  sobre el historial de la nota (`vault/kernel/historia.py::versiones`) y la
  huella del cuerpo (`vault/kernel/contenido.py::huella_de_cuerpo`).
- **Tests**: `tests/test_parte_a_normas.py`, `tests/test_torti_documentacion.py`
  y `test_ap75_norma.py`.

## Lo que no dice

El historial fiable es `.history/`, que escribe el dueño antes de sobrescribir.
El change log no guarda cuerpos, así que no sirve para comparar; y un cambio
hecho a mano fuera de toda tool no deja versión. Por eso una decisión sin
versiones es no verificable: decir que está intacta sería adivinar.
