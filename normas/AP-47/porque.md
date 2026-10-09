# AP-47 — Artefacto derivado desfasado — el índice dejó de reflejar el disco

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-47 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_reindex.py::vault_reindex`; `vault_write` (ninguna función de `scripts/vault_write.py` nombra AP-47 en su cuerpo).
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-47 en su cuerpo); `scripts/vault_reindex.py::vault_reindex`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap47_indice_refleja_disco.py::test_la_norma_esta_registrada_con_enforcement_real`, `tests/test_ap47_indice_refleja_disco.py::test_el_audit_reporta_el_indice_desfasado`, `tests/test_ap47_indice_refleja_disco.py::test_el_audit_calla_cuando_el_indice_esta_al_dia`, `tests/test_audit_acciones_de_movimiento.py::test_la_nota_movida_cita_ap47`, `tests/test_grafo_refresco.py::test_el_gancho_del_grafo_esta_declarado_y_no_cuenta_como_cruce`.
