# AP-72 — Comentario que cita una decisión que no existe

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace del vídeo de Torti Code sobre documentación útil (fase 4 del plan del
2026-11-16): un comentario no repite lo que el código ya dice, dice el porqué y
apunta a la decisión registrada. El repositorio ya citaba su ADR del puente
desde el código, pero nada comprobaba que el ADR citado existiera, y en un vault
`vault_code_sync` daba por huérfano un `@vault:` que apuntaba a una decisión de
`03_Decisions/`, porque solo contaba las notas de `11_Code/`.

## Las caras

- **Repositorio** (guard): `scripts/vault_doc_sync.py::adr_citados_sin_fichero`,
  dentro de `vault_doc_sync --check`, que es una puerta.
- **Vault** (detección): `scripts/vault_code_sync.py::_decision_existente`, con
  el criterio de qué es una decisión de su dueño (`vault/kernel/contenido.py::es_adr`).
- **Tests**: `tests/test_torti_documentacion.py`.

## Lo que no dice

No dice si el comentario es bueno. Que un comentario no repita el código exige
leerlo contra el código, y un detector por parecido léxico sería un guard débil
que da verde sin medir. Ese hueco está declarado como `cobertura_descubierta`
en la metodología de documentación que publica `vault_sdd_init`
(`HUECOS_DE_METODOLOGIA`), con su motivo.
