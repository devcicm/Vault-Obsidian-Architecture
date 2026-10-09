# SP-04 — Sesión MCP por HTTP sin credencial — cualquier proceso local la abre

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra SP-04 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_produccion` (ninguna función de `scripts/vault_produccion.py` nombra SP-04 en su cuerpo); `vault_token_service` (ninguna función de `scripts/vault_token_service.py` nombra SP-04 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_mcp_http_seguridad.py::test_sp04_esta_catalogada_con_enforcement_real`, `tests/test_token_service_seguridad.py::test_sp04_cubre_el_servicio_de_tokens`.
