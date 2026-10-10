# AP-26 — Missing tags — nota de contenido sin tags

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-26 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`; `scripts/vault_ingest.py::_build_note`; `scripts/vault_preferences.py::vault_preferences_set`; `vault/autoria/frontmatter_completar.py::_valor`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_context_memory.py::test_lo_ingerido_entra_como_borrador_y_baja_integridad`.
