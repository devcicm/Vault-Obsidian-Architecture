# AP-34 — Relacion tipada huerfana — endpoint inexistente en el vault

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-34 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::_detect_graph_knowledge_antipatterns`, `scripts/vault_audit.py::vault_audit`; `scripts/vault_graph_merge.py::vault_graph_merge`, `scripts/vault_graph_merge.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_graph_merge_sugerencias.py::test_ap34_una_relacion_con_un_extremo_inexistente_se_declara_huerfana`.
