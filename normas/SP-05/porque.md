# SP-05 — Separación Ejecutor-Curador y trazabilidad de banderas en la Fábrica de Conocimiento

## Por qué existe

Formaliza en el estándar la arquitectura de circuito cerrado de `SPEC-04`
(Fábrica de Conocimiento) 100 % sobre Markdown, JSONL y Git, sin terceros, sin
bases de datos ni embeddings: los ejecutores levantan señales no bloqueantes
(`vault_ronda --flag` → `00_System/.flags.jsonl`) y solo el curador batch
(`vault_propagate --curate-plan/--curate-apply`) actualiza el conocimiento
canónico estampando `source_flags` y registrando la operación `curated`.

## Las caras

- **Aplica** (`tools_enforcing`): `scripts/vault_ronda.py::levantar_senal`, `vault/ciclo_de_vida/curacion.py::aplicar_curacion`.
- **Tests** (`tests/`): `normas/SP-05/test_sp05.py::test_sp05_circuito_cerrado_ejecutor_curador`, `tests/test_fabrica_conocimiento_fase_q.py::test_q_circuito_cerrado_completo_ejecutor_bandera_curador_contexto`.
