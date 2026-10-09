# SP-02 — Forward-link verification — buscar antes de linkar

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra SP-02 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_write` (ninguna función de `scripts/vault_write.py` nombra SP-02 en su cuerpo).
- **Detecta** (`tools_detecting`): `scripts/vault_graph.py::vault_graph`; `vault_audit` (ninguna función de `scripts/vault_audit.py` nombra SP-02 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_normas_enlaces_sin_solape.py::test_quien_receta_buscar_antes_de_linkar_cita_a_sp02`, `tests/test_normas_enlaces_sin_solape.py::test_ap22_no_se_atribuye_el_aviso_de_ghost_links`, `tests/test_vault_norms.py::test_has_session_protocol`.
