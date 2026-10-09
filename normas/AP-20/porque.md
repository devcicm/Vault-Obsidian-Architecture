# AP-20 — Deceptive skeleton (empty-list)

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-20 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap20_esqueleto_de_lista.py::test_ap20_una_lista_casi_vacia_se_rechaza_sin_escribir`, `tests/test_ap20_esqueleto_de_lista.py::test_ap20_una_lista_llena_pasa`, `tests/test_ap20_esqueleto_de_lista.py::test_ap20_una_vineta_vacia_no_se_traga_la_linea_siguiente`.
