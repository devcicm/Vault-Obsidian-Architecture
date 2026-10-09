# AP-59 — Núcleo declarado sin contraste

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-59 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_kernel.py::_baseline`, `scripts/vault_kernel.py::check`, `scripts/vault_kernel.py::freeze`, `scripts/vault_kernel.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_kernel.py::_baseline`, `scripts/vault_kernel.py::check`, `scripts/vault_kernel.py::freeze`, `scripts/vault_kernel.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_kernel.py::test_el_check_nombra_la_norma_ap_59_y_publica_lo_que_mide`.
