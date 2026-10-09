# CN-03 — Standard status vocabulary — vocabulario canónico de meta.status

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra CN-03 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra CN-03 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_vault_norms.py::test_has_naming_conventions`, `tests/test_vault_norms_audit.py::test_audit_detects_bad_status_cn03`, `tests/test_vault_sanacion.py::test_fase_6_cuenta_violaciones_del_runtime`.
