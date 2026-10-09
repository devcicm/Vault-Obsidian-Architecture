# SP-01 — Delete protocol — change_log obligatorio antes de eliminar

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra SP-01 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_change_log` (ninguna función de `scripts/vault_change_log.py` nombra SP-01 en su cuerpo).
- **Detecta** (`tools_detecting`): `scripts/vault_norms.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_vault_norms.py::test_has_session_protocol`.
