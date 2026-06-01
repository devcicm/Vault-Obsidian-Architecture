# Tool Contracts

**Perfil:** `full` | **Tools:** 67

_Generado automáticamente por vault_compact_contracts.py_


## Grupo 0 — misc

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_create` *(deprecated)* |  | `title` | 6 opcionales |
| `vault_dataset` |  | `command` | 7 opcionales |
| `vault_index` |  | — | 3 opcionales |
| `vault_io` | Shared file IO helpers for vault tools. | — | — |
| `vault_link_safety` | Shared wiki-link validation and extraction helpers for vault tools. | — | — |
| `vault_migrate` *(deprecated)* |  | `--source`, `--project` | 3 opcionales |
| `vault_render` *(deprecated)* |  | — | 5 opcionales |
| `vault_reorganize` *(deprecated)* |  | `action` | 2 opcionales |
| `vault_spec_memory` | vault_spec_memory.py — Unified spec-driven memory for the vault standard. | ` in line: call = line depth = call.count(` | 4 opcionales |
| `vault_tools` *(deprecated)* |  | `command` | 5 opcionales |

## Grupo 1 — Core

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_append` |  | `--path`, `--content` | 2 opcionales |
| `vault_diff` |  | — | 7 opcionales |
| `vault_list` |  | — | 3 opcionales |
| `vault_merge` |  | — | 3 opcionales |
| `vault_read` |  | `--path` | — |
| `vault_search` |  | `--query` | 2 opcionales |
| `vault_write` |  | `--folder` | 6 opcionales |

## Grupo 2 — Observabilidad

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_log_error` |  | `--type`, `--title`, `--description` | 5 opcionales |

## Grupo 3 — Patrones

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_pattern_list` |  | — | 3 opcionales |
| `vault_pattern_save` |  | `--project`, `--name`, `--type`, `--status` | 4 opcionales |

## Grupo 4 — Diagramas

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_diagram_save` |  | `--project`, `--title`, `--diagram_type`, `--category`, `--content` | 1 opcional |
| `vault_relation_add` |  | `--project`, `--from`, `--to`, `--relation_type` | 4 opcionales |

## Grupo 5 — Conocimiento

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_knowledge_get` |  | `--query` | 2 opcionales |
| `vault_knowledge_save` |  | `--category` | 6 opcionales |

## Grupo 6 — Salud

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_audit` |  | — | 3 opcionales |
| `vault_graph` |  | — | — |
| `vault_validate` |  | — | 3 opcionales |

## Grupo 7 — Runbooks

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_runbook_log` |  | `--path`, `--outcome` | 2 opcionales |
| `vault_runbook_save` |  | `--project`, `--title`, `--trigger`, `--category`, `--steps` | 2 opcionales |

## Grupo 8 — Infraestructura

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_env_save` |  | `--project`, `--environment`, `--vars` | 1 opcional |
| `vault_infra_map` |  | — | 2 opcionales |
| `vault_infra_save` |  | `--name`, `--type`, `--description`, `--config` | 5 opcionales |

## Grupo 9 — Migración

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_migrate_docs` |  | `--source_path`, `--project` | 3 opcionales |
| `vault_migrate_rollback` |  | `--report_path` | 1 opcional |

## Grupo 10 — Línea de tiempo

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_timeline` |  | — | 6 opcionales |

## Grupo 11 — Vista proyecto

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_project_overview` |  | `--project` | 3 opcionales |
| `vault_project_status` |  | `--project`, `--status`, `--summary` | 1 opcional |

## Grupo 12 — Código

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_code_map` |  | `--project` | — |
| `vault_code_module` |  | `--project` | 15 opcionales |
| `vault_code_query` |  | `--project` | 5 opcionales |
| `vault_code_relation` |  | `--project`, `--from_file`, `--to_file`, `--relation_type` | 2 opcionales |

## Grupo 13 — Backups

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_backup` |  | — | 2 opcionales |
| `vault_backup_list` |  | — | — |
| `vault_restore` |  | `--backup_name` | 1 opcional |

## Grupo 14 — Seguridad

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_security_scan` |  | `--path` | 4 opcionales |

## Grupo 15 — Índices

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_master_index` |  | — | — |
| `vault_reindex` |  | — | 3 opcionales |
| `vault_section_index` |  | `--folder` | 1 opcional |

## Grupo 16 — Bibliografía

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_bibliography_save` |  | `--title`, `--url`, `--summary`, `--source_type` | 3 opcionales |

## Grupo 17 — Drift

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_drift_detect` |  | `--path`, `--project` | 2 opcionales |

## Grupo 18 — Flujos

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_flow_save` |  | `--project`, `--name`, `--type`, `--description`, `--mermaid` | 7 opcionales |

## Grupo 19 — Requerimientos

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_requirement_save` |  | `--project`, `--title`, `--description`, `--type`, `--priority` | 5 opcionales |

## Grupo 20 — Tests

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_test_save` |  | `--project`, `--title`, `--test_type`, `--description` | 7 opcionales |

## Grupo 21 — IA Governance

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_ai_decision` |  | `--project`, `--title`, `--decision_type`, `--description`, `--rationale` | 7 opcionales |

## Grupo 22 — Versionado

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_standard_upgrade` |  | — | 7 opcionales |

## Grupo 23 — Change Log

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_change_log` |  | — | 10 opcionales |

## Grupo 24 — Data Quality

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_fundamentals` |  | — | 4 opcionales |
| `vault_quality_check` |  | — | 4 opcionales |

## Grupo 25 — Propagación

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_impact` |  | — | 4 opcionales |
| `vault_propagate` |  | — | 8 opcionales |

## Grupo 26 — Tokens

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_token_counter` | Client tool for the vault token counter service. | `--flow-id`, `--flow-id`, `--text`, `--text`, `--flow-id`, `--flow-id` | 11 opcionales |
| `vault_token_service` | Local token usage service for vault documentation flows. | — | 2 opcionales |
| `vault_tokens` |  | — | 5 opcionales |

## Grupo 27 — Session Delta y Tags

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_delta` |  | — | 4 opcionales |
| `vault_tags` |  | — | 4 opcionales |

## Grupo 28 — Normas y Etiquetas

| Tool | Descripción | Args requeridos | Args opcionales |
|---|---|---|---|
| `vault_code_tag` |  | — | 12 opcionales |
| `vault_norms` |  | — | 10 opcionales |
