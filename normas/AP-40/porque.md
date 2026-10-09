# AP-40 — Contrato publicado que la CLI rechaza

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-40 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_mcp_catalog.py::check_sync`, `scripts/vault_mcp_catalog.py::check_params`, `scripts/vault_mcp_catalog.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_mcp_catalog.py::check_sync`, `scripts/vault_mcp_catalog.py::check_params`, `scripts/vault_mcp_catalog.py::main`; `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-40 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_catalog_params.py::test_ap40_esta_en_el_catalogo_con_enforcement_real`, `tests/test_catalog_params.py::test_el_audit_de_normas_conoce_ap40`.
