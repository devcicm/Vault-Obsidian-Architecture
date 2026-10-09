# AP-02 — Proliferación de versiones del mismo documento

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-02 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::vault_audit`.
- **Cobertura parcial**: declarada en `norma.py` (`cobertura_parcial`).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap02_versiones_misma_carpeta.py::test_ap02_llega_al_informe_del_audit`, `tests/test_ap02_versiones_misma_carpeta.py::test_ap02_el_catalogo_dice_parcial_y_nombra_a_quien_la_mide`, `tests/test_skills_contract.py::test_rango_ap_usa_el_maximo_no_el_conteo`.
