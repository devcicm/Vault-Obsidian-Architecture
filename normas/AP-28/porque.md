# AP-28 — Missing frontmatter — nota sin bloque YAML

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-28 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault/autoria/frontmatter_completar.py::planificar`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`; `vault_validate` (ninguna función de `scripts/vault_validate.py` nombra AP-28 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap56_frontmatter_heal.py::test_ap56_y_ap28_se_distinguen_en_las_dos_direcciones`.
