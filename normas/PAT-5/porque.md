# PAT-5 — Frontmatter as provenance chain

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra PAT-5 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Patrón** (`tools_del_patron`): `vault_write` (ninguna función de `scripts/vault_write.py` nombra PAT-5 en su cuerpo); `vault_audit` (ninguna función de `scripts/vault_audit.py` nombra PAT-5 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_context_memory.py::test_lo_ingerido_entra_como_borrador_y_baja_integridad`.
