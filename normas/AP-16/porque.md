# AP-16 — Sin identificador de agente en frontmatter

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-16 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`, `scripts/vault_write.py::main`; `scripts/vault_frontmatter_completar.py::_valor`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap64_responsable.py::test_ap64_catalogo_y_contrato`, `tests/test_context_memory.py::test_ap16_bloquea_sin_agente`, `tests/test_context_memory.py::test_ap16_bloquea_ingesta_sin_agente`, `tests/test_context_memory.py::test_las_tools_que_escriben_declaran_sus_guardas`.
