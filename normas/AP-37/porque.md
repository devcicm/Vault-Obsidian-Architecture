# AP-37 — No-op silencioso — ok: true sin indicador de trabajo

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-37 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_noop_audit.py::_tool_spec`, `scripts/vault_noop_audit.py::scan`, `scripts/vault_noop_audit.py::freeze`, `scripts/vault_noop_audit.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_noop_audit.py::_tool_spec`, `scripts/vault_noop_audit.py::scan`, `scripts/vault_noop_audit.py::freeze`, `scripts/vault_noop_audit.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_noop_audit.py::test_ap37_esta_registrada`, `tests/test_noop_audit.py::test_la_baseline_existe_y_es_legible`, `tests/test_noop_audit.py::test_la_deuda_esta_saldada_y_la_norma_es_un_guard_duro`, `tests/test_noop_audit.py::test_la_baseline_esta_al_dia`, `tests/test_noop_audit.py::test_las_tools_nuevas_de_v39_cumplen_ap37`, `tests/test_norms_coherence.py::test_ap60_la_norma_esta_en_el_catalogo_y_se_distingue_de_las_dos`, `tests/test_voice.py::test_una_tool_real_devuelve_vault_says`.
