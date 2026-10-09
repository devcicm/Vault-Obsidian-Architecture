# AP-55 — El catálogo de normas se certifica a sí mismo

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-55 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_norms_coherence.py::scan`, `scripts/vault_norms_coherence.py::freeze`, `scripts/vault_norms_coherence.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_norms_coherence.py::scan`, `scripts/vault_norms_coherence.py::freeze`, `scripts/vault_norms_coherence.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_norms_coherence.py::test_c2_calla_cuando_la_afirmacion_si_tiene_traza`, `tests/test_norms_coherence.py::test_ap55_esta_en_el_catalogo_y_la_aplica_esta_tool`, `tests/test_norms_coherence.py::test_la_baseline_quedo_saldada_y_no_retirada`, `tests/test_norms_coherence.py::test_ap60_la_norma_esta_en_el_catalogo_y_se_distingue_de_las_dos`.
