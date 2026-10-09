# AP-39 — Vocabulario abierto sin memoria

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-39 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_write.py::_tag_suggestions`, `scripts/vault_write.py::vault_write`; `scripts/vault_tags.py::main`.
- **Detecta** (`tools_detecting`): `scripts/vault_tags.py::main`; `vault_norms` (ninguna función de `scripts/vault_norms.py` nombra AP-39 en su cuerpo).
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_ap39_registro_en_el_write_path.py::test_el_gancho_esta_declarado_y_dice_por_que`, `tests/test_tag_vocabulary.py::test_ap39_esta_en_el_catalogo_con_enforcement_real`, `tests/test_tag_vocabulary.py::test_ap39_declara_las_tools_que_lo_detectan`, `tests/test_vault_init.py::test_el_primer_pasa_el_content_gate`, `tests/test_vault_init.py::test_ninguna_violacion_al_arrancar`.
