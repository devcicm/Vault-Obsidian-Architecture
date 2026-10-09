# AP-42 — Tool publicada sin haberse ejecutado nunca

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-42 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_smoke.py::run_one`, `scripts/vault_smoke.py::freeze`, `scripts/vault_smoke.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_smoke.py::run_one`, `scripts/vault_smoke.py::freeze`, `scripts/vault_smoke.py::main`; `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-42 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_smoke.py::test_el_audit_reporta_la_deuda_congelada`, `tests/test_smoke.py::test_ap42_esta_en_el_catalogo`, `tests/test_smoke.py::test_la_baseline_en_disco_declara_su_norma`, `tests/test_vault_norms_audit.py::test_runtime_audit_no_arrastra_observabilidad_del_estandar`.
