# AP-44 — Verificación autoconsistente — la tool se certifica a sí misma

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-44 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_audit.py::_build_indexes`, `scripts/vault_audit.py::_detect_broken_links`, `scripts/vault_audit.py::_detect_missing_metadata`, `scripts/vault_audit.py::vault_audit`, `scripts/vault_audit.py::_audit_external_path`; `vault/grafo/graph_fix.py::classify_all_broken`; `vault_mermaid_reglas` (ninguna función de `vault/kernel/mermaid_reglas.py` nombra AP-44 en su cuerpo).
- **Detecta** (`tools_detecting`): `scripts/vault_norms.py::vault_norms_scan`, `scripts/vault_norms.py::vault_norms_apply`; `scripts/vault_audit.py::_build_indexes`, `scripts/vault_audit.py::_detect_broken_links`, `scripts/vault_audit.py::_detect_missing_metadata`, `scripts/vault_audit.py::vault_audit`, `scripts/vault_audit.py::_audit_external_path`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap44_verificacion_autoconsistente.py::test_la_norma_existe_y_no_es_manual`, `tests/test_kernel.py::test_vault_kernel_no_parsea_imports_por_su_cuenta`, `tests/test_norms_coherence.py::test_ap55_esta_en_el_catalogo_y_la_aplica_esta_tool`, `tests/test_puente_sin_hogar.py::test_los_guards_que_leen_el_fuente_siguen_el_alias_hasta_el_dueno`.
