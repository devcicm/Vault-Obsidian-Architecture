# AP-61 — El guard cae con el dato que vino a medir

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-61 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_excepcion_declarada.py::check`, `scripts/vault_excepcion_declarada.py::freeze`, `scripts/vault_excepcion_declarada.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_excepcion_declarada.py::check`, `scripts/vault_excepcion_declarada.py::freeze`, `scripts/vault_excepcion_declarada.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_excepcion_declarada.py::test_el_repo_no_tiene_deuda_de_AP_61`.
