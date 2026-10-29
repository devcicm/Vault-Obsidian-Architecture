# Disponibilidad de las tools

> **Documento derivado.** Sale de `vault_mcp_catalog.TOOLS_CATALOG`, del catálogo de producto (`vault.meta_toolkit.catalogo_producto`), de `vault-sandbox/00_System/tool-spec.json` y de `scripts/toolkit-audit-last.json`. Se regenera con `python scripts/vault_doc_sync.py --fix` y `--check` falla si diverge: lo escrito a mano aquí se pierde. El motivo de cada tool «de cuidado» vive en `vault_doc_sync.TOOLS_DE_CUIDADO`.

Responde tres preguntas sobre cada tool: **dónde se puede usar**, **si hay evidencia de que funciona** y **cuándo no debe usarse y por qué**.

## En una tabla

| Categoría | Cuántas | Dónde corre | Quién la usa |
|---|---|---|---|
| Operaciones del vault por CLI | 96 | `vault run <tool>` desde la wheel instalada; por MCP las que estén expuestas | agentes y personas con un vault |
| Operaciones del vault solo por MCP | 2 | servidor MCP (JavaScript nativo); `vault run` no las ejecuta | agentes por MCP |
| Mantenimiento del estándar | 29 | solo en un checkout de este repo (`python scripts/<tool>.py`); la wheel no las instala | quien mantiene el estándar |
| Internas | 19 | no son tools de un vault: librerías, registros o CLIs de diagnóstico del toolkit | nadie desde fuera |
| Archivadas | 5 | no se ejecutan; cada una nombra su reemplazo | nadie |

Las 127 activas son 96 + 2 + 29. Expuestas por el servidor MCP: **97**; las otras 30 se ejecutan por CLI o en el checkout.

`vault tools list` dice lo mismo desde la wheel: `class: runtime` con `installed: true` es lo que corre; `class: maintenance` con `installed: false` es del checkout, y `vault run` la rechaza con `not_runtime_operation`.

## 1. Disponibles y funcionales

«Ejemplo verificado» es el veredicto de `vault_toolkit_audit` (AP-42): el ejemplo documentado de la tool se ejecuta de verdad sobre una copia del sandbox y su envelope cubre el contrato. `OK` es evidencia de que funciona **en ese ejemplo**, no de que cubra todos los argumentos. «Escribe» indica que la tool declara efectos sobre disco.

### 1.1 Operaciones del vault por CLI (y por MCP si se indica)

| Tool | Grupo | MCP | Escribe | Ejemplo verificado |
|---|---|---|---|---|
| `vault_ai_decision` | IA Governance | sí | sí | OK |
| `vault_append` | Core | sí | sí | OK |
| `vault_arquitectura_en` | Memoria de Contexto | sí | no | OK |
| `vault_audit` | Salud del Vault | sí | no | OK |
| `vault_backup` | Backups | sí | sí | OK |
| `vault_backup_list` | Backups | sí | no | OK |
| `vault_bibliography_save` | Bibliografía | sí | sí | OK |
| `vault_bug_save` | Defectos y Cuarentena | sí | sí | OK |
| `vault_change_log` | Change Log | sí | sí | OK |
| `vault_code_map` | Código | sí | sí | OK |
| `vault_code_module` | Código | sí | sí | OK |
| `vault_code_query` | Código | sí | no | OK |
| `vault_code_relation` | Código | sí | sí | OK |
| `vault_code_sync` | Código | sí | sí | OK |
| `vault_context_pack` | Memoria de Contexto | sí | no | OK |
| `vault_delete` | Change Log | sí | sí | OK |
| `vault_delta` | Session Delta y Tags | sí | sí | OK |
| `vault_diagram_export` | Diagramas | sí | sí | OK |
| `vault_diagram_save` | Diagramas | sí | sí | OK |
| `vault_diff` | Core | sí | no | OK |
| `vault_drift_detect` | Drift Detection | sí | sí | OK |
| `vault_env_matrix` | Infraestructura | sí | sí | OK |
| `vault_env_save` | Infraestructura | sí | sí | OK |
| `vault_fix_brackets` | Corrección Automática | sí | sí | OK |
| `vault_flow_save` | Flujos | sí | sí | OK |
| `vault_folder_registry` | Gestión de Carpetas | sí | sí | OK |
| `vault_frontmatter_completar` | Corrección Automática | sí | sí | OK |
| `vault_frontmatter_heal` | Corrección Automática | sí | sí | OK |
| `vault_fuente_unica` | Salud del Vault | sí | sí | OK |
| `vault_fundamentals` | Data Quality | sí | sí | OK |
| `vault_gobernanza` | Salud del Vault | sí | no | NO-VERIFICABLE |
| `vault_graph` | Salud del Vault | sí | sí | OK |
| `vault_graph_fix` | Corrección Automática | sí | sí | OK |
| `vault_graph_inspect` | Salud del Vault | sí | no | OK |
| `vault_graph_merge` | Salud del Vault | sí | sí | OK |
| `vault_history_compact` | Versionado | sí | sí | OK |
| `vault_impact` | Propagación | sí | no | OK |
| `vault_incident_save` | Producción/SRE | sí | sí | OK |
| `vault_infra_map` | Infraestructura | sí | sí | OK |
| `vault_infra_save` | Infraestructura | sí | sí | OK |
| `vault_ingest` | Memoria de Contexto | sí | sí | OK |
| `vault_init` | Bootstrap | sí | sí | OK |
| `vault_knowledge_get` | Conocimiento | sí | no | OK |
| `vault_knowledge_save` | Conocimiento | sí | sí | OK |
| `vault_list` | Core | sí | no | OK |
| `vault_log_error` | Observabilidad | sí | sí | OK |
| `vault_master_index` | Índices | sí | sí | OK |
| `vault_merge` | Core | sí | sí | OK |
| `vault_mermaid_check` | Diagramas | sí | sí | OK |
| `vault_migrate_docs` | Migración | sí | sí | OK |
| `vault_migrate_rollback` | Migración | sí | sí | OK |
| `vault_model_profile` | Memoria de Contexto | sí | sí | OK |
| `vault_move` | Core | sí | sí | OK |
| `vault_ncr_save` | Riesgos/Calidad | sí | sí | OK |
| `vault_onboard` | Bootstrap | sí | sí | OK |
| `vault_pattern_list` | Patrones | sí | no | OK |
| `vault_pattern_save` | Patrones | sí | sí | OK |
| `vault_preferences` | Memoria de Contexto | sí | sí | OK |
| `vault_privacy_save` | Riesgos/Calidad | sí | sí | OK |
| `vault_project` | Vista del Proyecto | sí | sí | OK |
| `vault_project_overview` | Vista del Proyecto | sí | sí | OK |
| `vault_project_status` | Vista del Proyecto | sí | sí | OK |
| `vault_propagate` | Propagación | sí | sí | OK |
| `vault_qa_save` | Tests | sí | sí | OK |
| `vault_quality_check` | Data Quality | sí | sí | OK |
| `vault_quality_dashboard` | Tests | sí | sí | OK |
| `vault_quarantine` | Defectos y Cuarentena | sí | sí | OK |
| `vault_query_parse` | Memoria de Contexto | sí | no | OK |
| `vault_read` | Core | sí | no | OK |
| `vault_reindex` | Índices | sí | sí | OK |
| `vault_relation_add` | Diagramas | sí | sí | OK |
| `vault_release_save` | Release | sí | sí | OK |
| `vault_requirement_save` | Requerimientos | sí | sí | OK |
| `vault_restore` | Backups | sí | sí | OK |
| `vault_risk_save` | Riesgos/Calidad | sí | sí | OK |
| `vault_runbook_log` | Runbooks | sí | sí | OK |
| `vault_runbook_save` | Runbooks | sí | sí | OK |
| `vault_sanacion` | Skills | sí | no | OK |
| `vault_sdd_init` | Skills | sí | sí | OK |
| `vault_search` | Core | sí | no | OK |
| `vault_section` | Gestión de Carpetas | sí | sí | OK |
| `vault_section_index` | Índices | sí | sí | OK |
| `vault_security_scan` | Seguridad | sí | sí | OK |
| `vault_slo_save` | Producción/SRE | sí | sí | OK |
| `vault_standard_upgrade` | Versionado | sí | sí | OK |
| `vault_subgraph` | Memoria de Contexto | sí | no | OK |
| `vault_supersede` | Corrección Automática | sí | sí | OK |
| `vault_tags` | Session Delta y Tags | sí | sí | OK |
| `vault_test_save` | Tests | sí | sí | OK |
| `vault_timeline` | Línea de Tiempo | sí | no | OK |
| `vault_token_counter` | Tokens | sí | no | OK |
| `vault_token_service` | Tokens | no | sí | OK |
| `vault_tokens` | Tokens | sí | no | OK |
| `vault_undo` | Versionado | sí | sí | OK |
| `vault_validate` | Salud del Vault | sí | no | OK |
| `vault_write` | Core | sí | sí | OK |

### 1.2 Operaciones solo por MCP

Las sirve el servidor MCP con JavaScript nativo; `vault run` responde que no están instaladas en la CLI.

| Tool | Grupo | MCP | Escribe | Ejemplo verificado |
|---|---|---|---|---|
| `vault_backup_base64` | Backups | sí | sí | NO-VERIFICABLE |
| `vault_restore_base64` | Backups | sí | sí | NO-VERIFICABLE |

### 1.3 Mantenimiento del estándar (solo en el checkout)

Comprueban o regeneran este repositorio. **No** operan el vault de nadie y no están en la wheel; lanzarlas contra un vault real no es su uso.

| Tool | Grupo | MCP | Escribe | Ejemplo verificado |
|---|---|---|---|---|
| `vault_arch` | Normas | no | sí | OK |
| `vault_blame_audit` | Normas | no | sí | OK |
| `vault_blueprint` | Normas | no | sí | OK |
| `vault_changelog_check` | Normas | no | sí | OK |
| `vault_ciclos` | Normas | no | sí | OK |
| `vault_clones` | Normas | no | sí | OK |
| `vault_code_tag` | Normas | no | sí | OK |
| `vault_criterios` | Normas | no | sí | OK |
| `vault_doc_counts` | Normas | no | sí | OK |
| `vault_doc_staleness` | Normas | no | no | OK |
| `vault_doc_sync` | Normas | no | sí | OK |
| `vault_error_contract` | Normas | no | sí | OK |
| `vault_esquema` | Normas | no | sí | OK |
| `vault_excepcion_declarada` | Normas | no | sí | OK |
| `vault_fix_all` | Normas | no | sí | OK |
| `vault_foreign_check` | Normas | no | no | OK |
| `vault_gate` | Normas | no | no | OK |
| `vault_kernel` | Normas | no | sí | OK |
| `vault_metricas` | Normas | no | sí | OK |
| `vault_noop_audit` | Normas | no | sí | OK |
| `vault_norms` | Normas | no | sí | OK |
| `vault_norms_coherence` | Normas | no | sí | OK |
| `vault_procesos_git` | Normas | no | no | OK |
| `vault_produccion` | Normas | no | sí | OK |
| `vault_recursos` | Normas | no | sí | OK |
| `vault_servicio` | Normas | no | no | OK |
| `vault_smoke` | Normas | no | sí | OK |
| `vault_toolkit_audit` | Normas | no | sí | OK |
| `vault_voice` | Normas | no | sí | OK |

## 2. Sin evidencia de ejemplo

Activas, pero `vault_toolkit_audit` no puede ejercitarlas con un ejemplo de CLI. No significa que fallen: significa que esa puerta no las prueba, y el motivo es:

| Tool | Veredicto | Motivo |
|---|---|---|
| `vault_backup_base64` | NO-VERIFICABLE | c0: runtime node: su despacho lo ejercita el servidor MCP, no un smoke de CLI (vault_smoke.run_one lo exime por lo que es); c2: runtime node: su despacho lo ejercita el servidor MCP, no un smoke de CLI (vault_smoke.run_one lo exime por lo que es) |
| `vault_gobernanza` | NO-VERIFICABLE | c0: sin script propio: invocada por __module__ desde el servidor MCP; c2: sin script propio: invocada por __module__ desde el servidor MCP |
| `vault_restore_base64` | NO-VERIFICABLE | c0: runtime node: su despacho lo ejercita el servidor MCP, no un smoke de CLI (vault_smoke.run_one lo exime por lo que es); c2: runtime node: su despacho lo ejercita el servidor MCP, no un smoke de CLI (vault_smoke.run_one lo exime por lo que es) |

## 3. Úsalas con cuidado

Activas y funcionales, pero cambian o borran estado. Léelas antes de lanzarlas y, si tienen `--dry-run`, empieza por ahí.

| Tool | Dónde corre | Por qué cuidado |
|---|---|---|
| `vault_delete` | wheel (`vault run`) | Borra la nota (o la manda a `20_Quarantine/` con `--trash-only`); deja change-log y copia en `.history/`, y `--dry-run` muestra el efecto antes. |
| `vault_fix_all` | checkout | Regenera artefactos derivados del checkout del estándar (catálogos, planos, documentación); no es de un vault. |
| `vault_history_compact` | wheel (`vault run`) | Con `--apply` borra versiones de `.history/` (conserva las N más recientes); lo borrado no se recupera. |
| `vault_mermaid_check` | wheel (`vault run`) | Con `--fix` (sin `--dry-run`) reescribe los `.md` cuyo bloque Mermaid corrige. |
| `vault_migrate_rollback` | wheel (`vault run`) | Revierte una migración ya hecha; exige `confirm`. |
| `vault_quarantine` | wheel (`vault run`) | Mueve la nota a `20_Quarantine/` y anota el movimiento en el libro append-only; `--restore` la devuelve. |
| `vault_restore` | wheel (`vault run`) | Sobrescribe archivos del vault con los de una copia; exige `confirm`. |
| `vault_restore_base64` | MCP | Restaura a un directorio nuevo sin tocar el original; exige `--confirm true`. Cuidado con el espacio que ocupa, no con el original. |
| `vault_undo` | wheel (`vault run`) | Por defecto restaura sin sobrescribir; con `--force` sobrescribe la nota actual. |

## 4. No las uses

### 4.1 Archivadas

Siguen en el registro por la política de no-derogación (se anota el reemplazo, no se borra). No se ejecutan; usa el reemplazo.

| Tool | Usa en su lugar | Motivo |
|---|---|---|
| `vault_create` | `vault_write` | Superseded por vault_write, que conserva su contrato. |
| `vault_migrate` | `vault_migrate_docs` | Superseded por vault_migrate_docs y vault_migrate_rollback. |
| `vault_render` | `vault_diagram_save` | Superseded por vault_diagram_save; para exportar el diagrama usa vault_diagram_export. |
| `vault_reorganize` | `vault_migrate_docs` | Superseded por vault_migrate_docs; para mover una nota usa vault_move y para el registro de carpetas vault_folder_registry. |
| `vault_tools` | See individual tools | Superseded por el catálogo MCP (vault_mcp_catalog). |

### 4.2 Internas

Existen en `scripts/` pero no son tools de un vault: librerías, registros o utilidades del propio toolkit. Ni la CLI ni el servidor MCP las publican.

| Tool | Motivo |
|---|---|
| `vault_compact_contracts` | Compacta contratos para inspección; su salida es material de análisis del estándar, no una nota del vault. |
| `vault_dataset` | Manipula datasets de prueba fuera del modelo de notas. |
| `vault_distribution_sync` | Genera adaptadores instalables desde los registros canónicos; mantiene el toolkit, no opera conocimiento del runtime. |
| `vault_entorno` | No es tool del catalogo: es el registro canonico de las variables de entorno (AP-05) y su CLI publica presupuesto y help. Su consumidor es quien configura la shell, no un vault. |
| `vault_errors` | Catálogo de códigos de error y su CLI de consulta. Es infraestructura que consumen todas las tools, no una capacidad del vault: publicarla daría a un agente una tool cuyo efecto sobre el vault es ninguno. |
| `vault_index` | Superseded por vault_reindex y vault_master_index, que son las publicadas. |
| `vault_link_safety` | Librería de validación de enlaces que consumen las tools de grafo; sin CLI. |
| `vault_manifest` | Lee y valida el manifiesto del estándar, no el vault. |
| `vault_mcp` | Arranque y diagnóstico del propio servidor MCP. Su superficie es el transporte, no el vault. |
| `vault_mcp_catalog` | Mantiene el toolkit, no el vault: sincroniza el catálogo y corre las puertas de cierre de CLAUDE.md. Se ejecuta en el repo del estándar, donde no hay vault que gobernar, así que no pertenece a la superficie que se expone a un agente. |
| `vault_registry` | Registro canónico de secciones. Es la fuente de verdad que importan las tools; sin CLI. |
| `vault_release` | es un invariante del repo (fabrica del bump de version), no una tool de vault: misma clase que vault_doc_counts |
| `vault_secret_scan` | Librería del gancho de secretos del write path (vault_write_hook); su CLI es de diagnóstico para escanear un .md o un directorio y no es un camino de acceso del agente. |
| `vault_spec_catalog_check` | Guard de coherencia del catálogo de la spec. Mismo caso que vault_mcp_catalog: opera sobre el estándar. |
| `vault_spec_generate_catalog` | Generador del catálogo de la spec. Opera sobre el estándar, no sobre un vault. |
| `vault_spec_memory` | Memoria de trabajo sobre la spec, interna al desarrollo del estándar. |
| `vault_spec_validate` | Valida la spec contra su propio esquema; opera sobre el estándar. |
| `vault_test_runner` | Lanza la suite del repo; es tooling de desarrollo. |
| `vault_test_scope` | Arnés de desarrollo: el alcance de tests que toca un cambio, para cerrar sin arrastrar la suite entera. Mantiene el toolkit, no el vault: no se publica en el catálogo MCP. |
