# AP-09 — Runbooks fuera de estructura

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-09 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_norms.py::vault_norms_scan`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_vault_norms_audit.py::test_audit_detects_runbook_out_of_place_ap09`.
