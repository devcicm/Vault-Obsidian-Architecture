# AP-45 — Cobertura sin evidencia — la nota existe para llenar la sección

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-45 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_onboard.py::_write`, `scripts/vault_onboard.py::vault_onboard`, `scripts/vault_onboard.py::main`; `vault_write` (ninguna función de `scripts/vault_write.py` nombra AP-45 en su cuerpo).
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-45 en su cuerpo); `scripts/vault_audit.py::_detect_empty_indexes`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap45_cobertura_sin_evidencia.py::test_ap45_esta_en_el_catalogo_con_enforcement_real`.
