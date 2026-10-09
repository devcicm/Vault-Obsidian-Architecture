# AP-46 — Frontmatter a mano — cada tool es su propio escritor

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-46 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_io.py::_verificar_frontmatter`; `scripts/vault_write.py::generate_frontmatter`.
- **Detecta** (`tools_detecting`): `scripts/vault_norms.py::vault_norms_apply`, `scripts/vault_norms.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap46_escritores_migrados.py::test_ap46_vault_write_conserva_texto_y_escribe_legible`, `tests/test_ap46_interpolacion_cruda.py::test_ningun_title_ni_project_se_interpola_crudo`, `tests/test_ap46_write_path_unico.py::test_la_norma_esta_en_el_catalogo_y_no_es_manual`, `tests/test_ap46_write_path_unico.py::test_el_audit_reporta_la_nota_con_el_bloque_sin_cerrar`, `tests/test_ap46_write_path_unico.py::test_el_audit_no_reporta_una_nota_bien_formada`, `tests/test_norms_coherence.py::test_un_helper_que_existe_no_es_c1_pero_se_publica_aparte`, `tests/test_vault_sanacion.py::test_fase_6_cuenta_violaciones_del_runtime`.
