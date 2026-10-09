# AP-57 — Criterio con dueño, reimplementado en la medida

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-57 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_criterios.py::_baseline`, `scripts/vault_criterios.py::check`, `scripts/vault_criterios.py::freeze`, `scripts/vault_criterios.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_criterios.py::_baseline`, `scripts/vault_criterios.py::check`, `scripts/vault_criterios.py::freeze`, `scripts/vault_criterios.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap57_criterios.py::test_check_no_reporta_deuda_congelada_como_nueva`, `tests/test_ap57_criterios.py::test_ap57_esta_en_el_catalogo_con_enforcement_real_y_distincion_reciproca`, `tests/test_criterios_fronteras.py::test_una_copia_nueva_en_frontera_rompe_la_puerta`, `tests/test_criterios_fronteras.py::test_la_norma_declara_la_frontera_en_su_prevencion`, `tests/test_grafo_import.py::test_los_llamadores_delegan_en_el_dueno`.
