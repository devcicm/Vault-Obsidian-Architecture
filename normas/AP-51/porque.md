# AP-51 — La tool culpa al dato de su propio fallo

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-51 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_blame_audit.py::catch_silenciosos_js`, `scripts/vault_blame_audit.py::scan`, `scripts/vault_blame_audit.py::freeze`, `scripts/vault_blame_audit.py::migrate`, `scripts/vault_blame_audit.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_blame_audit.py::catch_silenciosos_js`, `scripts/vault_blame_audit.py::scan`, `scripts/vault_blame_audit.py::freeze`, `scripts/vault_blame_audit.py::migrate`, `scripts/vault_blame_audit.py::main`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap51_culpar_al_dato.py::test_la_baseline_esta_congelada_y_el_repo_no_ha_crecido`, `tests/test_ap51_culpar_al_dato.py::test_la_norma_esta_registrada_con_enforcement_real`, `tests/test_ap51_culpar_al_dato.py::test_freeze_no_se_ejecuta_por_error_al_solo_comprobar`, `tests/test_baseline.py::test_la_pendiente_de_una_baseline_del_repo_sale_de_git`, `tests/test_baseline.py::test_sin_git_la_pendiente_lo_dice_en_vez_de_devolver_serie_vacia`.
