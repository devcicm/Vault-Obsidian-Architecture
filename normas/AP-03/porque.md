# AP-03 — Stubs sin política de expansión

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-03 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::_detect_stubs_sin_plazo`, `scripts/vault_audit.py::_detect_empty_indexes`, `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_normas_de_audit_ejercitadas.py::test_ap03_ve_la_seccion_cuyo_indice_es_un_stub`, `tests/test_normas_de_audit_ejercitadas.py::test_ap03_no_ve_stub_donde_no_hay_indice`, `tests/test_pat2_stub_con_plazo.py::test_pat2_el_audit_ve_el_stub_sin_plazo_y_el_vencido`.
