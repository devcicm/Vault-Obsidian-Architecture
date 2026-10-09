# AP-18 — Cross-folder content duplication

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-18 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_capa4_audit_ejercitada.py::test_ap18_ve_el_contenido_identico_entre_carpetas`.
