# AP-19 — Shadow indexing

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-19 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-19 en su cuerpo).
- **Tests** (`tests/`): ninguno la ejercita en el cuerpo de un `test_*`.
