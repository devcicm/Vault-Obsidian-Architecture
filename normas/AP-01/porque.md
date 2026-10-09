# AP-01 — Documentación alucinada

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-01 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_drift_detect.py::vault_drift_vigencia`.
- **Cobertura parcial**: declarada en `norma.py` (`cobertura_parcial`).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap01_codigo_inexistente.py::test_ap01_files_que_no_existe_se_nombra`, `tests/test_ap01_codigo_inexistente.py::test_ap01_el_catalogo_nombra_al_detector`, `tests/test_ap01_prosa.py::test_ap01_la_ruta_citada_en_prosa_que_no_existe_se_nombra`, `tests/test_ap01_prosa.py::test_ap01_la_cobertura_parcial_declara_la_prosa_medida`, `tests/test_ap46_editores.py::test_ap46_aplicar_una_norma_respeta_una_lista_en_bloque`, `tests/test_norms_coherence.py::test_ap60_un_discriminador_vacio_tampoco_salda`, `tests/test_skills_catalogo.py::test_rango_desfasado_se_reporta_con_el_fichero`, `tests/test_skills_catalogo.py::test_cuerpo_e_indice_desfasados_se_reportan_los_dos`, y 2 más (la capa 4 de `vault_blueprint` los publica todos).
