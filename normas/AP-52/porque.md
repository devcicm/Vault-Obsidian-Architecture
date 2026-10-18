# AP-52 — El error se emite fuera del contrato del catalogo

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-52 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_error_contract.py::scan`, `scripts/vault_error_contract.py::freeze`, `scripts/vault_error_contract.py::migrate`, `scripts/vault_error_contract.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_error_contract.py::scan`, `scripts/vault_error_contract.py::freeze`, `scripts/vault_error_contract.py::migrate`, `scripts/vault_error_contract.py::main`.
- **Cobertura parcial**: declarada en `norma.py` (`cobertura_parcial`).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap52_contrato_de_error.py::test_la_baseline_esta_congelada_y_al_dia`, `tests/test_ap52_contrato_de_error.py::test_la_deuda_de_ap52_esta_saldada`, `tests/test_ap52_contrato_de_error.py::test_la_norma_esta_registrada_con_enforcement_real`, `tests/test_ap52_contrato_de_error.py::test_la_norma_tiene_seccion_en_el_manifiesto`, `tests/test_regla7_contraste_ajeno.py::test_el_self_test_verifica_las_cuatro_negativas`.
