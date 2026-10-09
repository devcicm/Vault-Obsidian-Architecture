# AP-41 — Máquina de estados declarada sin verificar

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-41 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`.
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-41 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_status_machine.py::test_una_transicion_ilegal_se_rechaza`, `tests/test_status_machine.py::test_el_audit_reporta_la_transicion_ilegal_del_historial`, `tests/test_status_machine.py::test_el_audit_no_inventa_violaciones_en_un_historial_legal`, `tests/test_status_machine.py::test_el_audit_ordena_por_marca_de_tiempo_no_por_nombre`, `tests/test_status_machine.py::test_ap41_esta_en_el_catalogo_con_enforcement_real`, `tests/test_voice.py::test_una_tool_de_escritura_tiene_normas_que_la_gobiernan`, `tests/test_voice.py::test_cuando_una_norma_frena_la_llamada_la_voz_nombra_esa_norma`.
