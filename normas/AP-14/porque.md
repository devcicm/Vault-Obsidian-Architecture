# AP-14 — Wiki-links rotos o vacíos

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-14 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_write` (ninguna función de `scripts/vault_write.py` nombra AP-14 en su cuerpo); `scripts/vault_move.py::_mover_nota`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`; `scripts/vault_graph.py::vault_graph`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_audit_acciones_de_movimiento.py::test_la_nota_borrada_con_entrantes_cita_ap14`, `tests/test_normas_enlaces_sin_solape.py::test_ap14_no_cuenta_como_roto_el_enlace_con_carpeta`, `tests/test_normas_enlaces_sin_solape.py::test_la_distincion_ap14_ap21_no_contradice_a_vault_move`, `tests/test_norms_coherence.py::test_c4_no_confunde_una_ponderacion_con_una_contradiccion`.
