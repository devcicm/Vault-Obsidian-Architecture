# AP-05 — Múltiples fuentes de verdad para el mismo dato

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-05 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_fuente_unica.py::medir`, `scripts/vault_fuente_unica.py::_baseline`, `scripts/vault_fuente_unica.py::check`, `scripts/vault_fuente_unica.py::freeze`, `scripts/vault_fuente_unica.py::main`.
- **Cobertura parcial**: declarada en `norma.py` (`cobertura_parcial`).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap05_fuente_unica.py::test_ap05_ya_no_esta_descubierta`, `tests/test_ap46_editores.py::test_ap46_aplicar_una_norma_respeta_una_lista_en_bloque`, `tests/test_blueprint.py::test_ap05_sigue_declarada_pendiente_y_nombrada`, `tests/test_js_native_frontera.py::test_el_comentario_del_mjs_sigue_registrando_por_que`, `tests/test_norms_coherence.py::test_c2_muerde_cuando_el_modulo_no_nombra_la_norma`, `tests/test_norms_coherence.py::test_freeze_se_niega_a_congelar_deuda_sin_precedente`.
