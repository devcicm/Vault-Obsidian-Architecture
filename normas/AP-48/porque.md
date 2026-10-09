# AP-48 — Implementación paralela por camino de acceso

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-48 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_mcp_catalog.py::check_contracts`.
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-48 en su cuerpo); `scripts/vault_mcp_catalog.py::check_contracts`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap48_implementacion_paralela.py::test_la_norma_existe_y_tiene_enforcement_real`, `tests/test_ap48_implementacion_paralela.py::test_ninguna_nativa_tiene_script_python`.
