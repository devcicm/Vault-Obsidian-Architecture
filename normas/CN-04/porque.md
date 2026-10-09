# CN-04 — Note opens with its title — la nota abre con su título como H1

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote PAT+SP+CN).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra CN-04 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::vault_write`; `vault_knowledge_save` (ninguna función de `scripts/vault_knowledge_save.py` nombra CN-04 en su cuerpo); `scripts/vault_ai_decision.py::vault_ai_decision`.
- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::_detect_convenciones_cn01_cn04`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_cn01_cn04_audit_informativo.py::test_cn01_cn04_se_publican_sin_peso`, `tests/test_cn04_escritores_con_titulo.py::test_la_nota_que_crea_el_escritor_abre_con_h1`, `tests/test_cn04_nota_abre_con_titulo.py::test_cn04_esta_catalogada_con_sus_tools`.
