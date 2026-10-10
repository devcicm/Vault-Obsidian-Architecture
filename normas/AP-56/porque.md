# AP-56 — Frontmatter presente que el consumidor no puede leer

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-56 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::generate_frontmatter`; `vault/autoria/frontmatter_heal.py::main`.
- **Detecta** (`tools_detecting`): `vault/autoria/frontmatter_heal.py::main`; `scripts/vault_foreign_check.py::contrastar`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap56_frontmatter_heal.py::test_ap56_esta_en_el_catalogo_con_enforcement_real`, `tests/test_ap56_frontmatter_heal.py::test_ap56_y_ap28_se_distinguen_en_las_dos_direcciones`.
