# AP-58 — Ciclo esquivado con un import diferido

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-58 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_ciclos.py::_baseline`, `scripts/vault_ciclos.py::check`, `scripts/vault_ciclos.py::freeze`, `scripts/vault_ciclos.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_ciclos.py::_baseline`, `scripts/vault_ciclos.py::check`, `scripts/vault_ciclos.py::freeze`, `scripts/vault_ciclos.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ciclos.py::test_contar_las_diferidas_es_lo_que_destapa_el_ciclo`, `tests/test_ciclos.py::test_ap58_esta_en_el_catalogo_con_enforcement_real`, `tests/test_ciclos.py::test_la_puerta_existe_y_apunta_a_la_tool`, `tests/test_ciclos.py::test_la_baseline_esta_publicada_en_el_plano`, `tests/test_ciclos.py::test_el_envelope_declara_su_limite`.
