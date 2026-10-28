# Gobierno del estándar

_Derivado de los registros canónicos. Se regenera con `python scripts/vault_servicio.py --doc` y no se edita a mano: lo escrito aquí se pierde (AP-47)._

## El servicio y sus tres capacidades

- **Escritura → gobernanza** (`escritura_a_gobernanza`) — Lo que el agente captura queda escrito una sola vez, normalizado contra las normas, versionado y auditable después. Sirve a: `memoria_documental_gobernada`.
- **Consulta → contexto** (`consulta_a_contexto`) — Una pregunta del agente se convierte en un paquete de contexto acotado y presupuestado, recorriendo el grafo del vault sin índice externo. Sirve a: `memoria_documental_gobernada`.
- **Gobernanza del estándar** (`gobernanza_del_estandar`) — El estándar cumple lo que publica: registro canónico primero, doc derivada, guard que falla si divergen. Ninguna de estas tools toca las notas de un usuario. Sirve a: `memoria_documental_gobernada`.

## Las cuatro familias de normas

83 normas vivas, cada una un paquete en `normas/<código>/`. El catálogo derivado completo está en [docs/sdd/04-antipatterns.md](sdd/04-antipatterns.md).

- **AP** · Anti-patrón — Un fallo con nombre, señal, prevención y límites. La unidad normativa principal. (77 vigentes).
- **PAT** · Patrón — La forma recomendada de resolver algo que el estándar ya resolvió mal una vez. (6 vigentes).
- **SP** · Protocolo de sesión — Reglas de proceso entre el agente y el vault durante una sesión. (0 vigentes).
- **CN** · Convención — Un acuerdo de nomenclatura o forma que mantiene el vault legible y predecible. (0 vigentes).

## La escalera de enforcement

- **guard** (13 normas) — Falla en el punto de uso: la tool se niega a hacerlo mal.
- **guard+audit** (32 normas) — Y además una puerta la mide sobre el repo entero.
- **audit** (32 normas) — Una puerta la mide; se arregla en el siguiente ciclo.
- **recommended** (6 normas) — Se publica, no se fuerza. La cobertura débil se declara.

## Qué es ley para quién

- **Para quien usa el vault**: las normas, aplicadas por las tools de escritura y consulta — contrato de nota, vocabulario de estados, protocolo de borrado.
- **Para quien mantiene este repositorio**: la gobernanza del meta-toolkit — el conjunto de tools cuya naturaleza es `meta_estandar` (29), que miden este repo y no el vault de nadie, por las 27 puertas de `docs/PUERTAS.md`.

## La superficie que ve el agente por MCP

El catálogo marca `exposed_via_mcp` y el servidor MCP lo respeta: las 29 tools de gobernanza **no** llegan al cliente (el recorte lo deriva de la capacidad `gobernanza_del_estandar`, no de una lista escrita a mano). `VAULT_MCP_PERFIL=agente` reduce el menú a las 14 del protocolo de sesión, y el servidor poda además en runtime las tools cuyo script no existe.

## El mapa: capacidad → grupo → tool

### Escritura → gobernanza — 88 tools (`escritura_a_gobernanza`)

- **Backups (13)** — vault_backup, vault_backup_base64, vault_backup_list, vault_restore, vault_restore_base64
- **Bibliografía (16)** — vault_bibliography_save
- **Bootstrap (31)** — vault_init, vault_onboard
- **Change Log (23)** — vault_change_log, vault_delete
- **Conocimiento (5)** — vault_knowledge_get, vault_knowledge_save
- **Core (1)** — vault_append, vault_diff, vault_list, vault_merge, vault_move, vault_read, vault_search, vault_write
- **Corrección Automática (33)** — vault_fix_brackets, vault_frontmatter_completar, vault_frontmatter_heal, vault_graph_fix, vault_supersede
- **Código (12)** — vault_code_map, vault_code_module, vault_code_query, vault_code_relation, vault_code_sync
- **Data Quality (24)** — vault_fundamentals, vault_quality_check
- **Defectos y Cuarentena (36)** — vault_bug_save, vault_quarantine
- **Diagramas (4)** — vault_diagram_export, vault_diagram_save, vault_mermaid_check, vault_relation_add
- **Drift Detection (17)** — vault_drift_detect
- **Flujos (18)** — vault_flow_save
- **Gestión de Carpetas (32)** — vault_folder_registry, vault_section
- **IA Governance (21)** — vault_ai_decision
- **Infraestructura (8)** — vault_env_matrix, vault_env_save, vault_infra_map, vault_infra_save
- **Línea de Tiempo (10)** — vault_timeline
- **Migración (9)** — vault_migrate_docs, vault_migrate_rollback
- **Observabilidad (2)** — vault_log_error
- **Patrones (3)** — vault_pattern_list, vault_pattern_save
- **Producción/SRE (28)** — vault_incident_save, vault_slo_save
- **Propagación (25)** — vault_impact, vault_propagate
- **Release (29)** — vault_release_save
- **Requerimientos (19)** — vault_requirement_save
- **Riesgos/Calidad (30)** — vault_ncr_save, vault_privacy_save, vault_risk_save
- **Runbooks (7)** — vault_runbook_log, vault_runbook_save
- **Salud del Vault (6)** — vault_audit, vault_fuente_unica, vault_gobernanza, vault_graph, vault_graph_inspect, vault_graph_merge, vault_validate
- **Seguridad (14)** — vault_security_scan
- **Session Delta y Tags (27)** — vault_delta, vault_tags
- **Skills (37)** — vault_sanacion, vault_sdd_init
- **Tests (20)** — vault_qa_save, vault_quality_dashboard, vault_test_save
- **Versionado (22)** — vault_history_compact, vault_standard_upgrade, vault_undo
- **Vista del Proyecto (11)** — vault_project, vault_project_overview, vault_project_status
- **Índices (15)** — vault_master_index, vault_reindex, vault_section_index

### Consulta → contexto — 10 tools (`consulta_a_contexto`)

- **Memoria de Contexto (34)** — vault_arquitectura_en, vault_context_pack, vault_ingest, vault_model_profile, vault_preferences, vault_query_parse, vault_subgraph
- **Tokens (26)** — vault_token_counter, vault_token_service, vault_tokens

### Gobernanza del estándar — 29 tools (`gobernanza_del_estandar`)

- **Normas (35)** — vault_arch, vault_blame_audit, vault_blueprint, vault_changelog_check, vault_ciclos, vault_clones, vault_code_tag, vault_criterios, vault_doc_counts, vault_doc_staleness, vault_doc_sync, vault_error_contract, vault_esquema, vault_excepcion_declarada, vault_fix_all, vault_foreign_check, vault_gate, vault_kernel, vault_metricas, vault_noop_audit, vault_norms, vault_norms_coherence, vault_procesos_git, vault_produccion, vault_recursos, vault_servicio, vault_smoke, vault_toolkit_audit, vault_voice

## El vocabulario y su dueño

- **`meta.status`** (12 valores) — `vault_norms_catalog.STATUS_VOCAB`.
- **Secciones del vault y su clase documental** — `vault_registry`.
- **Instantáneas congeladas** — `vault_io.SNAPSHOT_DIRS`.
- **Material ajeno al vault** (`node_modules`, cachés) — `vault_io.DIRECTORIOS_AJENOS`.
- **Los verbos de git que el toolkit ejecuta** — `vault/kernel/procesos_git.py` (AP-68).
- **Las causas del dominio** — `vault/kernel/fallos.py`.
- **Los códigos de error y su recuperación** — `ERROR_CATALOG` en `vault/kernel/errores.py`.

## Cómo se lee una norma

1. `normas/<código>/norma.py` — la declaración: qué fallo es, severidad, enforcement, de qué se distingue.
2. `porque.md` — por qué existe y qué dejó fuera, con el alcance declarado.
3. `guard.py` / `heal.py` — apuntan a las funciones que la aplican: derivados, no escritura.
4. El `test_*.py` del paquete la ejercita.
5. La versión pública completa: [docs/sdd/04-antipatterns.md](sdd/04-antipatterns.md).

## Quién responde

- **Por el estándar**: el mantenedor que declara el banner del manifiesto — **CARLOS IVAN CM**. No hay segunda instancia: cada release pasa por una invocación explícita de `vault_release --nueva-version`, y el autor del commit lo deja registrado en git — la misma fuente que selló el hash del changelog.
- **Por cada decisión de arquitectura**: el `Responsable:` declarado en cada ADR de `docs/adr/` — CARLOS IVAN CM. AP-64 aplicado al propio repo (v41.21): un ADR sin responsable no es una decisión, es una intención.
- **Por cada duda de norma**: el catálogo (`vault_norms --show <código>`) y el `porque.md` del paquete, que declara qué quedó fuera y por qué.
- **Por cada promesa al consumidor**: el ejercedor que declara `vault_produccion`; por cada propiedad afirmada, la puerta o el instrumento de `AFIRMADAS`.

## Las puertas

La gobernanza se ejerce por 27 puertas de cierre, una por registro. El porqué de cada una está en [docs/PUERTAS.md](PUERTAS.md), derivado de `vault_gate.PUERTAS`.
