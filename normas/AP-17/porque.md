# AP-17 — Canonical-shadow duplication

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-17 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `vault_supersede` (ninguna función de `vault/autoria/supersede.py` nombra AP-17 en su cuerpo).
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Cobertura parcial**: declarada en `norma.py` (`cobertura_parcial`).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_blueprint.py::test_la_deuda_de_ap17_no_afirma_lo_que_el_catalogo_desmiente`, `tests/test_normas_caras.py::test_un_sanador_que_no_nombra_la_norma_falla_la_forma`, `tests/test_normas_de_audit_ejercitadas.py::test_ap17_ve_el_par_canonico_y_su_sombra`.
