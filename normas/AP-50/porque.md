# AP-50 — Decisión duplicada sin dueño declarado

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-50 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_arch` (ninguna función de `scripts/vault_arch.py` nombra AP-50 en su cuerpo).
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-50 en su cuerpo); `vault_arch` (ninguna función de `scripts/vault_arch.py` nombra AP-50 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap57_criterios.py::test_ap57_esta_en_el_catalogo_con_enforcement_real_y_distincion_reciproca`.
