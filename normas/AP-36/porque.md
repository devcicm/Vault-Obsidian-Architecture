# AP-36 — Contención e idempotencia — side-effects fuera del vault o no rastreables

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-36 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_section_index.py::main`; `scripts/vault_io.py::assert_within_vault`, `scripts/vault_io.py::_rechazar_traversal`.
- **Detecta** (`tools_detecting`): `scripts/vault_norms.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap46_heal.py::test_en_seco_no_escribe_nada`, `tests/test_arquitectura.py::test_la_contencion_ap36_es_invariante_del_contexto`, `tests/test_ciclo_de_vida_dominio.py::test_el_repositorio_no_deja_salir_del_vault`, `tests/test_consulta_dominio.py::test_el_repositorio_no_deja_salir_del_vault`, `tests/test_gobernanza_dominio.py::test_el_repositorio_no_deja_salir_del_vault`, `tests/test_grafo_dominio.py::test_el_repositorio_no_deja_salir_del_vault`, `tests/test_indices_dominio.py::test_el_repositorio_no_deja_salir_del_vault`, `tests/test_mcp_http_seguridad.py::test_sp04_esta_catalogada_con_enforcement_real`, y 10 más (la capa 4 de `vault_blueprint` los publica todos).
