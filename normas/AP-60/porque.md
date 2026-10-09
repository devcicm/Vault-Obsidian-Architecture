# AP-60 — El guard cobra por declarar y regala el silencio

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-60 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_norms_coherence.py::scan`, `scripts/vault_norms_coherence.py::freeze_distincion`, `scripts/vault_norms_coherence.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_norms_coherence.py::scan`, `scripts/vault_norms_coherence.py::freeze_distincion`, `scripts/vault_norms_coherence.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap08_prosa_universo.py::test_ap08_declara_el_universo_vacio_de_la_parte_en_prosa`, `tests/test_norms_coherence.py::test_ap60_la_baseline_viva_solo_encoge`, `tests/test_norms_coherence.py::test_ap60_la_norma_esta_en_el_catalogo_y_se_distingue_de_las_dos`.
