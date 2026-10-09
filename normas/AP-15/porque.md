# AP-15 — Archivos externos depositados en la raíz del vault

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-15 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`; `vault_move` (ninguna función de `scripts/vault_move.py` nombra AP-15 en su cuerpo); `scripts/vault_section_index.py::vault_section_index`.
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-15 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_normas_sin_registro_a_mano.py::test_ap15_la_cumplen_las_tools_que_rechazan_la_raiz`, `tests/test_vault_norms_audit.py::test_audit_detects_root_file_ap15`.
