# CN-02 — Numbered folder structure — secciones numeradas como únicos destinos

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra CN-02 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::problemas_de_meta`, `scripts/vault_write.py::vault_write`; `vault/indices/registro_de_secciones.py::listar`, `vault/indices/registro_de_secciones.py::main`; `scripts/vault_move.py::_destino_invalido`, `scripts/vault_move.py::_reclasificacion`, `scripts/vault_move.py::move_folder`.
- **Detecta** (`tools_detecting`): `scripts/vault_section_index.py::vault_section_index`; `scripts/vault_norms.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_blueprint.py::test_el_nombre_de_la_tool_se_lee_aunque_llegue_decorado`, `tests/test_raiz_no_seccion.py::test_docs_en_la_raiz_ya_no_se_denuncia`, `tests/test_raiz_no_seccion.py::test_una_carpeta_de_verdad_ajena_si_se_denuncia`, `tests/test_vault_norms.py::test_has_naming_conventions`, `tests/test_vault_norms_audit.py::test_audit_detects_adhoc_folder_cn02`.
