# AP-62 — El consumidor paga el fan-out del productor

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-62 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_recursos.py::_baseline`, `scripts/vault_recursos.py::check`, `scripts/vault_recursos.py::freeze`, `scripts/vault_recursos.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_recursos.py::_baseline`, `scripts/vault_recursos.py::check`, `scripts/vault_recursos.py::freeze`, `scripts/vault_recursos.py::main`; `vault_arch` (ninguna función de `scripts/vault_arch.py` nombra AP-62 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_recursos.py::test_la_norma_esta_catalogada_con_guard`, `tests/test_recursos.py::test_la_norma_declara_de_que_se_distingue`.
