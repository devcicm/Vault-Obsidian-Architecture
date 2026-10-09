# AP-32 — Relaciones tipadas sin predicate valido en la ontologia

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-32 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_graph_merge.py::_merge_entity_relations`, `scripts/vault_graph_merge.py::vault_graph_merge`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_graph_merge_sugerencias.py::test_ap32_un_predicado_desconocido_no_se_sustituye_por_el_parecido`.
