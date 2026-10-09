# AP-25 — Mermaid diagram syntax errors — nodos/tipos no definidos

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-21..AP-40).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-25 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Detecta** (`tools_detecting`): `scripts/vault_audit.py::_detect_mermaid_errors`, `scripts/vault_audit.py::vault_audit`; `scripts/vault_mermaid_check.py::check_file`, `scripts/vault_mermaid_check.py::scan_vault`.
- **Tests** (`tests/`, criterio de la capa 4): `tests/test_skills_catalogo.py::test_cuerpo_e_indice_desfasados_se_reportan_los_dos`, `tests/test_vault_norms.py::test_ap25_mermaid_registered`.
