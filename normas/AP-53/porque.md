# AP-53 — El historial se afirma a mano y nadie lo contrasta con git

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-53 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_changelog_check.py::_cargar_baseline`, `scripts/vault_changelog_check.py::congelar`.
- **Detecta** (`tools_detecting`): `scripts/vault_changelog_check.py::_cargar_baseline`, `scripts/vault_changelog_check.py::congelar`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_changelog_check.py::test_ap53_esta_en_el_catalogo_de_normas`.
