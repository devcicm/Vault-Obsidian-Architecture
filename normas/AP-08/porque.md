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
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap08_version_pinned.py::test_ap08_version_pinned_es_campo_opcional_del_contrato_v41`, `tests/test_ap08_version_pinned.py::test_ap08_vigencia_nombra_la_nota_anclada_a_una_version_que_ya_paso`, `tests/test_ap08_vigencia.py::test_ap08_vigencia_nombra_la_nota_que_no_acompano_al_cambio`.

## Por qué no es un guard

Sigue en `audit` a propósito (Parte A del plan de estrés, L3, 2026-11-17). AP-08 es
un desfase en el tiempo: la nota queda vieja cuando cambia el código que describe,
y eso ocurre después de escribirla, en un commit que no pasa por el vault. En el
momento de la escritura la nota acompaña al código por definición; lo que se mide
es la distancia entre su `updatedAt` y el último commit de sus `files:`, y entre su
`version_pinned:` y el manifiesto del repo, y las dos solo existen más tarde
(`vault_drift_detect --mode vigencia`).
