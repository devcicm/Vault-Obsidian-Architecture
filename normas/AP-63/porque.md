# AP-63 — El nombre de un proyecto como texto libre

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-63 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_project.py::auditar`, `scripts/vault_project.py::sanar`, `scripts/vault_project.py::_ficha_nueva`, `scripts/vault_project.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_project.py::auditar`, `scripts/vault_project.py::sanar`, `scripts/vault_project.py::_ficha_nueva`, `scripts/vault_project.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_project_registrado.py::test_ap63_ningun_project_nuevo_sin_resolver`, `tests/test_vault_project.py::test_ap63_audit_nombra_fantasmas_y_claves_no_canonicas`.
