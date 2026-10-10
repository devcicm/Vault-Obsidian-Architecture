# AP-22 — Wiki-link vacío — [[]] sin destino

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-22 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::_check_content_gate`, `scripts/vault_write.py::_content_gate_reason`, `scripts/vault_write.py::_check_bracket_balance`, `scripts/vault_write.py::vault_write`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::_detect_malformed_wikilinks`, `scripts/vault_audit.py::vault_audit`; `vault/autoria/fix_brackets.py::_analyze_note`, `vault/autoria/fix_brackets.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_normas_caras.py::test_ap22_y_ap24_las_repara_fix_brackets`, `tests/test_normas_caras.py::test_una_cara_editada_a_mano_se_detecta`, `tests/test_normas_enlaces_sin_solape.py::test_ap14_no_cuenta_como_roto_el_enlace_con_carpeta`, `tests/test_normas_enlaces_sin_solape.py::test_ap22_declara_de_que_se_distingue`, `tests/test_normas_enlaces_sin_solape.py::test_ap22_no_se_atribuye_el_aviso_de_ghost_links`, `tests/test_norms_coherence.py::test_c4_muerde_sobre_la_inversion_real_de_ap22`, `tests/test_norms_coherence.py::test_c4_calla_sobre_el_catalogo_corregido`, `tests/test_norms_coherence.py::test_c5_muerde_cuando_la_distincion_es_de_una_sola_parte`, y 3 más (la capa 4 de `vault_blueprint` los publica todos).
