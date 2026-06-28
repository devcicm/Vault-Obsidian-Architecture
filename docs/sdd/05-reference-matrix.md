# Reference Matrix -- Matriz de Referencia

> Tabla cross-reference: antipatrón → herramienta que detecta → herramienta que arregla.
> Cross-reference table: antipattern → detecting tool → fixing tool.

---

## ES

| Antipattern | Detecta | Arregla | Previene |
|---|---|---|---|
| AP-11 Skeleton files | vault_validate | vault_write (re-create) | content gate |
| AP-13 Timestamps inválidos | vault_audit | vault_write (regenera) | frontmatter schema |
| AP-14 Wiki-links rotos | vault_audit --broken-links | (manual) | SP-02 forward-link verification |
| AP-17 Canonical-shadow | vault_audit | vault_deduplicate | vault_code_module AP-17 guard |
| AP-18 Cross-folder dup | vault_audit | vault_deduplicate | migration idempotent |
| AP-21 Path-anchored links | vault_write (guard) | vault_write (reject) | content gate |
| AP-22 Empty wikilinks | vault_write (guard) | vault_write (reject) | content gate |
| AP-23 Note > 500 lines | vault_write (advisory) | (manual split) | guidelines |
| AP-24 Bracket imbalance | vault_write (guard) + vault_audit | vault_render_check --fix | content gate |
| AP-25 Mermaid errors | vault_audit + vault_mermaid_check | (manual) | vault_mermaid_check |

---

## EN

| Antipattern | Detects | Fixes | Prevents |
|---|---|---|---|
| AP-11 Skeleton files | vault_validate | vault_write (re-create) | content gate |
| AP-13 Invalid timestamps | vault_audit | vault_write (regenerate) | frontmatter schema |
| AP-14 Broken wiki-links | vault_audit --broken-links | (manual) | SP-02 forward-link verification |
| AP-17 Canonical-shadow | vault_audit | vault_deduplicate | vault_code_module AP-17 guard |
| AP-18 Cross-folder dup | vault_audit | vault_deduplicate | migration idempotent |
| AP-21 Path-anchored links | vault_write (guard) | vault_write (reject) | content gate |
| AP-22 Empty wikilinks | vault_write (guard) | vault_write (reject) | content gate |
| AP-23 Note > 500 lines | vault_write (advisory) | (manual split) | guidelines |
| AP-24 Bracket imbalance | vault_write (guard) + vault_audit | vault_render_check --fix | content gate |
| AP-25 Mermaid errors | vault_audit + vault_mermaid_check | (manual) | vault_mermaid_check |
