# AP-08 — Documentación anclada a versiones obsoletas

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-08 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_drift_detect.py::vault_drift_vigencia`, `scripts/vault_drift_detect.py::main`.
- **Cobertura parcial**: declarada en `norma.py` (`cobertura_parcial`).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap08_prosa_universo.py::test_ninguna_tool_del_estandar_escribe_version_pinned`, `tests/test_ap08_vigencia.py::test_ap08_vigencia_nombra_la_nota_que_no_acompano_al_cambio`.
