# AP-38 — Vocabulario validado después de escribir, no antes

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-38 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::generate_frontmatter`, `scripts/vault_write.py::vault_write`; `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-38 en su cuerpo).
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-38 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_status_vocabulary.py::test_ninguna_tool_emite_status_sin_pasar_por_el_registro`.
