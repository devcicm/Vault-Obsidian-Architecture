# AP-11 — Skeleton files — frontmatter válido, contenido vacío

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-11 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`.
- **Detecta** (`tools_detecting`): `vault_audit` (ninguna función de `scripts/vault_audit.py` nombra AP-11 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_envelope_forma.py::test_completar_conserva_lo_propio_y_no_pisa_lo_canonico`, `tests/test_voice.py::test_una_tool_de_escritura_tiene_normas_que_la_gobiernan`, `tests/test_voice.py::test_una_tool_real_devuelve_vault_says`.
