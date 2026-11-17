# AP-07 — ADRs incompletos

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-07 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_norms.py::vault_norms_scan`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap07_criterio_adr.py::test_ap07_la_auditoria_usa_el_mismo_criterio`, `tests/test_ap64_responsable.py::test_ap64_catalogo_y_contrato`, `tests/test_vault_norms_audit.py::test_audit_detects_incomplete_adr_ap07`, `tests/test_vault_norms_audit.py::test_audit_adr_stub_exempt_ap07`, `tests/test_vault_norms_audit.py::test_audit_bom_frontmatter_parsed`.

## Guard en la frontera de mutación (v41.27)

Desde la Parte A del plan de estrés (L3, 2026-11-17) la norma es `guard+audit`.
El guard vive en el dueño de la escritura,
`scripts/vault_io.py::_exigir_decision_cerrada_valida`, con el criterio de
`vault/kernel/contenido.py::secciones_faltantes_al_cerrar`: la escritura que deja
un ADR cerrado o terminal sin Contexto, Decisión y Consecuencias se rechaza con
`VALIDATION_FAILED` y la plantilla (`plantilla_adr`) en la pista. Un borrador sigue
pudiendo estar incompleto mientras se discute. Una nota que ya existía no se
bloquea hasta que se reescribe su cuerpo o se cierra: cambiar solo su frontmatter
—el `superseded_by` de `vault_supersede`— es la salida y sigue abierta. Tests:
`tests/test_parte_a_normas.py`.
