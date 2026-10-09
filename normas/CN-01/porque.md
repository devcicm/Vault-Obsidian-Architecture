# CN-01 — Kebab-case filenames — nombres de archivo en minúsculas con guiones

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra CN-01 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::generate_frontmatter`, `scripts/vault_write.py::vault_write`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::_detect_convenciones_cn01_cn04`, `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap46_escritores_migrados.py::test_ap46_el_indice_de_tags_y_los_hubs_nacen_legibles`, `tests/test_cn01_cn04_audit_informativo.py::test_cn01_cn04_se_publican_sin_peso`, `tests/test_cn04_escritores_con_titulo.py::test_la_nota_que_crea_el_escritor_abre_con_h1`, `tests/test_meta_contrato.py::test_el_autor_del_bloque_no_deja_que_meta_lo_pise`, `tests/test_vault_norms.py::test_has_naming_conventions`.
