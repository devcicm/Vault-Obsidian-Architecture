# AP-12 — Frontmatter inconsistente entre notas del mismo tipo

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-12 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::generate_frontmatter`; `scripts/vault_frontmatter_completar.py::_valor`.
- **Detecta** (`tools_detecting`): `vault_validate` (ninguna función de `scripts/vault_validate.py` nombra AP-12 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_capa4_audit_ejercitada.py::test_ap12_el_contrato_y_el_scan_ven_la_nota_sin_id`.
