# AP-29 — Missing status field — nota sin estado de ciclo de vida

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-29 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault/autoria/frontmatter_completar.py::_valor`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`; `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-29 en su cuerpo).
- **Tests** (`tests/`): ninguno la ejercita en el cuerpo de un `test_*`.
