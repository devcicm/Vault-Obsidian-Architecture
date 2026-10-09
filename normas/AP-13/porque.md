# AP-13 — Timestamps inválidos o incompletos en frontmatter

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-13 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::generate_frontmatter`, `scripts/vault_write.py::vault_write`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_meta_contrato.py::test_ap13_las_fechas_salen_del_reloj_en_iso_completo`.
