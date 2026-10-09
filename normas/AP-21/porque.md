# AP-21 — Path-anchored wiki-links

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-21 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::_check_content_gate`, `scripts/vault_write.py::_content_gate_reason`, `scripts/vault_write.py::vault_write`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap21_dentro_de_fence.py::test_el_ejemplo_en_fence_no_dispara_el_scan_de_safety`, `tests/test_ap21_dentro_de_fence.py::test_fuera_del_fence_si_dispara`, `tests/test_ap21_ruta_necesaria.py::test_vault_write_sigue_rechazando_la_ruta_que_sobra_o_no_resuelve`, `tests/test_ap21_ruta_necesaria.py::test_los_detectores_de_ap21_usan_el_mismo_criterio`, `tests/test_ap21_ruta_necesaria.py::test_vault_audit_marca_el_nombre_que_resuelve_a_varias_notas`, `tests/test_normas_enlaces_sin_solape.py::test_ap14_no_cuenta_como_roto_el_enlace_con_carpeta`, `tests/test_normas_enlaces_sin_solape.py::test_la_distincion_ap14_ap21_no_contradice_a_vault_move`, `tests/test_vault_regex.py::test_path_anchored_error`.
