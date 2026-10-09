# AP-43 — Norma sin refuerzo en el punto de uso

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-43 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_voice` (ninguna función de `scripts/vault_voice.py` nombra AP-43 en su cuerpo); `vault_errors` (ninguna función de `scripts/vault_errors.py` nombra AP-43 en su cuerpo).
- **Detecta** (`tools_detecting`): `vault_voice` (ninguna función de `scripts/vault_voice.py` nombra AP-43 en su cuerpo); `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-43 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap39_registro_en_el_write_path.py::test_el_gancho_esta_declarado_y_dice_por_que`, `tests/test_vault_norms_audit.py::test_runtime_audit_no_arrastra_observabilidad_del_estandar`, `tests/test_voice.py::test_el_audit_reporta_una_norma_muda`, `tests/test_voice.py::test_ap43_esta_en_el_catalogo`.
