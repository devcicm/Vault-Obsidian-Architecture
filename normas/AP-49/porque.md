# AP-49 — Vínculo resuelto en tiempo de import

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-41..AP-63).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-49 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_arch.py::check`, `scripts/vault_arch.py::freeze`.
- **Detecta** (`tools_detecting`): `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-49 en su cuerpo); `scripts/vault_arch.py::check`, `scripts/vault_arch.py::freeze`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_arquitectura.py::test_las_normas_salen_del_catalogo`, `tests/test_durabilidad_dominio.py::test_el_adaptador_no_decide_nada`.
