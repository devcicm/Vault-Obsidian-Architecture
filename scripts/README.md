# Vault Scripts

Scripts Python del estándar **Vault Obsidian Architecture v29**. Implementan las 59 tools activas del vault como ejecutables CLI independientes + módulo de observabilidad.

- **68 archivos** — 59 tools activas + 5 deprecadas + 4 internas + 4 meta + `vault_errors.py`
- **Python 3.9+** requerido — sin dependencias externas obligatorias
- **VAULT_ROOT** = `Path(__file__).parent.parent` — apunta a la raíz del vault; todos los `--folder`/`--path` se validan con `assert_within_vault()` para prevenir escrituras fuera del vault
- **Timeout automático** — todas las tools terminan en ≤60s (configurable via `VAULT_TOOL_TIMEOUT` env var)
- **JSON siempre** — cualquier error devuelve `{"ok": false, "error_code": "...", "recovery": {...}}`
- **Frontmatter v29** — todas las notas generadas incluyen `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`
- **Escrituras atómicas** — notas y JSON críticos usan `atomic_write_text`/`atomic_write_json` de `vault_io.py`

---

## Índice por grupo

| Grupo | Scripts |
|---|---|
| [Grupo 1 — Core](#grupo-1--core) | vault_write, vault_read, vault_search, vault_list, vault_append, vault_diff, vault_merge |
| [Grupo 2 — Observabilidad](#grupo-2--observabilidad) | vault_log_error |
| [Grupo 3 — Patrones](#grupo-3--patrones) | vault_pattern_save, vault_pattern_list |
| [Grupo 4 — Diagramas y Cardinalidad](#grupo-4--diagramas-y-cardinalidad) | vault_diagram_save, vault_relation_add |
| [Grupo 5 — Conocimiento](#grupo-5--conocimiento) | vault_knowledge_save, vault_knowledge_get |
| [Grupo 6 — Salud del Vault](#grupo-6--salud-del-vault) | vault_audit, vault_validate, vault_graph |
| [Grupo 7 — Runbooks](#grupo-7--runbooks) | vault_runbook_save, vault_runbook_log |
| [Grupo 8 — Infraestructura](#grupo-8--infraestructura) | vault_infra_save, vault_infra_map, vault_env_save |
| [Grupo 9 — Migración](#grupo-9--migración) | vault_migrate_docs, vault_migrate_rollback |
| [Grupo 10 — Línea de Tiempo](#grupo-10--línea-de-tiempo) | vault_timeline |
| [Grupo 11 — Vista del Proyecto](#grupo-11--vista-del-proyecto) | vault_project_status, vault_project_overview |
| [Grupo 12 — Código](#grupo-12--código) | vault_code_module, vault_code_relation, vault_code_map, vault_code_query |
| [Grupo 13 — Backups](#grupo-13--backups) | vault_backup, vault_backup_list, vault_restore |
| [Grupo 14 — Seguridad](#grupo-14--seguridad) | vault_security_scan |
| [Grupo 15 — Índices](#grupo-15--índices) | vault_section_index, vault_master_index, vault_reindex |
| [Grupo 16 — Bibliografía](#grupo-16--bibliografía) | vault_bibliography_save |
| [Grupo 17 — Drift Detection](#grupo-17--drift-detection) | vault_drift_detect |
| [Grupo 18 — Flujos](#grupo-18--flujos) | vault_flow_save |
| [Grupo 19 — Requerimientos](#grupo-19--requerimientos) | vault_requirement_save |
| [Grupo 20 — Tests](#grupo-20--tests) | vault_test_save |
| [Grupo 21 — IA Governance](#grupo-21--ia-governance) | vault_ai_decision |
| [Grupo 22 — Versionado del Estándar](#grupo-22--versionado-del-estándar) | vault_standard_upgrade |
| [Grupo 23 — Change Log](#grupo-23--change-log) | vault_change_log |
| [Grupo 24 — Data Quality](#grupo-24--data-quality) | vault_quality_check, vault_fundamentals |
| [Grupo 25 — Propagación](#grupo-25--propagación) | vault_impact, vault_propagate |
| [Grupo 26 — Tokens](#grupo-26--tokens) | vault_tokens, vault_token_counter, vault_token_service |
| [Grupo 27 — Session Delta y Tags](#grupo-27--session-delta-y-tags) | vault_delta, vault_tags |
| [Observabilidad de Tools](#observabilidad-de-tools) | vault_errors |
| [Utilidades internas](#utilidades-internas) | vault_index, vault_dataset, vault_io, vault_link_safety |
| [Deprecadas](#deprecadas) | vault_create, vault_migrate, vault_reorganize, vault_tools, vault_render |
| [Meta / Build](#meta--build) | vault_manifest, vault_compact_contracts, vault_test_runner, vault_spec_memory |

---

## Grupo 1 — Core

### `vault_write.py`
Crea o actualiza una nota con frontmatter YAML correcto. Versiona en `.history/` antes de sobreescribir. Actualiza `search-index.json` y regenera el section index automáticamente. Guards AP-20 (bullets vacíos) y AP-21 (wiki-links con ruta).

```bash
python vault_write.py --folder "01_Projects/mi-api" --title "Status" --content "# Status\n\nActivo"
python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags "arch,backend" --meta '{"status":"accepted"}'
python vault_write.py --folder "03_Decisions" --title "ADR-001" --content "..." --meta-file meta.json
```

| Parámetro | Requerido | Descripción |
|---|---|---|
| `--folder` | sí | Ruta relativa al vault root |
| `--title` | sí | Título de la nota |
| `--content` | sí | Contenido Markdown. Usar `@file:ruta` para leer de archivo |
| `--tags` | no | Lista de etiquetas |
| `--meta` | no | JSON adicional para frontmatter |
| `--meta-file` | no | Ruta a JSON con frontmatter adicional (evita problemas de quoting en PowerShell) |

---

### `vault_read.py`
Lee una nota del vault por ruta relativa o por título.

```bash
python vault_read.py --path "01_Projects/mi-api/status.md"
python vault_read.py --title "Status"
```

---

### `vault_search.py`
Búsqueda full-text en `search-index.json` con score ponderado.

```bash
python vault_search.py --query "circuit breaker"
python vault_search.py --query "deploy" --project "mi-api"
python vault_search.py --query "error" --folder "02_Observability"
```

---

### `vault_list.py`
Lista notas de una carpeta del vault.

```bash
python vault_list.py
python vault_list.py --folder "01_Projects"
python vault_list.py --folder "02_Observability/errors"
```

---

### `vault_append.py`
Agrega contenido al final de una nota existente (modo append-only). Útil para changelogs y session logs.

```bash
python vault_append.py --path "01_Projects/mi-api/changelog.md" --content "## v1.2\n\nFix deploy"
python vault_append.py --path "04_Sessions/2026-05-09.md" --content "Completado ADR-003" --section "## Tasks"
```

---

### `vault_diff.py`
Muestra el historial de versiones de una nota comparando versiones en `.history/`.

```bash
python vault_diff.py --path "01_Projects/mi-api/overview.md"
python vault_diff.py --path "01_Projects/mi-api/overview.md" --version "2"
```

---

### `vault_merge.py`
Detecta y resuelve duplicados entre vaults o dentro del mismo vault.

```bash
python vault_merge.py --action detect
python vault_merge.py --source "/path/to/other-vault" --action merge --conflict skip
python vault_merge.py --action dedup   # hacer vault_backup primero
```

---

## Grupo 2 — Observabilidad

### `vault_log_error.py`
Registra errores, antipatrones, vulnerabilidades, métricas, alertas y SLOs en `02_Observability/`.

```bash
python vault_log_error.py --type error --title "SSH Timeout" --description "..." --severity high
python vault_log_error.py --type antipattern --title "N+1 Query" --description "..." --severity medium --project mi-api
python vault_log_error.py --type vulnerability --title "API Key Exposed" --severity critical
python vault_log_error.py --type metric --title "Response Time P99" --description "..." --severity info \
  --meta '{"service":"api","value":"245ms","unit":"ms","objective":"200ms"}'
python vault_log_error.py --type slo --title "API Availability" --description "..." --severity info \
  --meta '{"sli":"requests < 500","objective":99.9,"window":"30d"}'
```

| `--type` | Carpeta destino |
|---|---|
| `error` | `02_Observability/errors/` |
| `antipattern` | `02_Observability/antipatterns/` |
| `vulnerability` | `02_Observability/vulnerabilities/` |
| `metric` | `02_Observability/metrics/` |
| `alert` | `02_Observability/alerts/` |
| `slo` | `02_Observability/slos/` |

---

## Grupo 3 — Patrones

### `vault_pattern_save.py`
Documenta un patrón de diseño, arquitectura, código o integración en `05_Patterns/`.

```bash
python vault_pattern_save.py --project mi-api --title "Circuit Breaker" --category code \
  --problem "Fallos en cascada" --solution "..." --implementation "..."
```

| `--category` | Carpeta |
|---|---|
| `design` | `05_Patterns/design/` |
| `architecture` | `05_Patterns/architecture/` |
| `code` | `05_Patterns/code/` |
| `integration` | `05_Patterns/integration/` |

---

### `vault_pattern_list.py`
Lista todos los patrones documentados, opcionalmente filtrados por proyecto o categoría.

```bash
python vault_pattern_list.py --project mi-api
python vault_pattern_list.py --category architecture
```

---

## Grupo 4 — Diagramas y Cardinalidad

### `vault_diagram_save.py`
Guarda diagramas Mermaid, ASCII o PlantUML en `06_Diagrams/`.

```bash
python vault_diagram_save.py --project mi-api --title "Auth Flow" --diagram_type mermaid \
  --category sequence --content "sequenceDiagram\n  Client->>Server: POST /login"
```

| `--category` | Carpeta |
|---|---|
| `entity` | `06_Diagrams/entity/` |
| `component` | `06_Diagrams/component/` |
| `sequence` | `06_Diagrams/sequence/` |
| `dependency` | `06_Diagrams/dependency/` |
| `flow` | `06_Diagrams/flow/` |

---

### `vault_relation_add.py`
Agrega una relación entre entidades y auto-regenera el ERD Mermaid en `06_Diagrams/entity/`.

```bash
python vault_relation_add.py --project mi-api --from "User" --to "Order" \
  --relation_type has_many --cardinality "1:N"
python vault_relation_add.py --project mi-api --from "ServiceA" --to "ServiceB" \
  --relation_type calls
```

| `--relation_type` | Símbolo Mermaid |
|---|---|
| `has_one`, `has_many`, `belongs_to`, `many_to_many` | ERD |
| `implements`, `extends`, `depends_on`, `uses`, `calls`, `owns`, `aggregates` | Graph TD |

---

## Grupo 5 — Conocimiento

### `vault_knowledge_save.py`
Documenta conocimiento de dominio en `07_Knowledge/` con categoría explícita.

```bash
python vault_knowledge_save.py --project mi-api --title "Stripe Webhooks" --category api \
  --content "# Stripe Webhooks\n\n..."
python vault_knowledge_save.py --project mi-api --title "CQRS" --category concept --content "..."
```

| `--category` | Carpeta |
|---|---|
| `glossary` | `07_Knowledge/glossary/` |
| `api` | `07_Knowledge/apis/` |
| `concept` | `07_Knowledge/concepts/` |
| `business-rule` | `07_Knowledge/business-rules/` |
| `config` | `07_Knowledge/configs/` |
| `dependency` | `07_Knowledge/dependencies/` |
| `framework` | `07_Knowledge/frameworks/` |

---

### `vault_knowledge_get.py`
Busca notas de conocimiento con score ponderado. Auto-lee el contenido si hay exactamente 1 resultado con score ≥ 60.

```bash
python vault_knowledge_get.py --query "Stripe API"
python vault_knowledge_get.py --query "CQRS" --category concept
python vault_knowledge_get.py --query "postgres" --project mi-api
```

---

## Grupo 6 — Salud del Vault

### `vault_audit.py`
Audita la salud del vault: notas vacías, orphans, broken links, notas stale, AP-17 (títulos similares), AP-18 (contenido duplicado cross-folder). Retorna health score 0–100.

```bash
python vault_audit.py
python vault_audit.py --project mi-api
```

**Score:** `100 - (vacías×2) - (sin_fm×3) - (broken_links×2) - (stale×1)`

| Score | Estado |
|---|---|
| 90–100 | Excelente |
| 70–89 | Bien |
| 50–69 | Necesita atención |
| < 50 | Crítico |

---

### `vault_validate.py`
Valida frontmatter YAML, campos requeridos y estructura de carpetas nota a nota.

```bash
python vault_validate.py
python vault_validate.py --check frontmatter
python vault_validate.py --check structure
python vault_validate.py --check indexes
```

---

### `vault_graph.py`
Genera `99_Index/graph.json` con nodos (notas), aristas (wiki-links), orphans y broken links.

```bash
python vault_graph.py
python vault_graph.py --project mi-api
```

---

## Grupo 7 — Runbooks

### `vault_runbook_save.py`
Documenta un runbook operacional en `08_Runbooks/`.

```bash
python vault_runbook_save.py --project mi-api --title "Deploy a Producción" --category deploy \
  --content "# Deploy\n\n## Pasos\n1. ..."
```

| `--category` | Carpeta |
|---|---|
| `deploy` | `08_Runbooks/deploy/` |
| `debug` | `08_Runbooks/debug/` |
| `setup` | `08_Runbooks/setup/` |
| `rollback` | `08_Runbooks/rollback/` |
| `maintenance` | `08_Runbooks/maintenance/` |
| `pipeline` | `08_Runbooks/pipeline/` |
| `incident` | `08_Runbooks/incident/` |

---

### `vault_runbook_log.py`
Registra la ejecución de un runbook (quién lo ejecutó, cuándo, resultado).

```bash
python vault_runbook_log.py --runbook "deploy/mi-api-deploy" \
  --status success --notes "Deploy v1.4.2 sin incidentes"
```

---

## Grupo 8 — Infraestructura

### `vault_infra_save.py`
Documenta un componente de infraestructura en `09_Infrastructure/`.

```bash
python vault_infra_save.py --project mi-api --name "server-01" --type server \
  --ip "192.168.1.10" --environment production --description "Servidor principal"
python vault_infra_save.py --project mi-api --name "postgres" --type database \
  --port 5432 --environment production
```

| `--type` | Carpeta |
|---|---|
| `server` | `09_Infrastructure/servers/` |
| `service` | `09_Infrastructure/services/` |
| `database` | `09_Infrastructure/databases/` |
| `network` | `09_Infrastructure/network/` |
| `container` | `09_Infrastructure/containers/` |
| `pipeline` | `09_Infrastructure/pipelines/` |
| `secret` | `09_Infrastructure/secrets/` |

---

### `vault_infra_map.py`
Genera el mapa de infraestructura Mermaid en `09_Infrastructure/infra-map.md` desde `.infra-index.json`.

```bash
python vault_infra_map.py --project mi-api
```

---

### `vault_env_save.py`
Documenta variables de entorno por ambiente en `01_Projects/{project}/envs.md`. Nunca guarda valores reales.

```bash
python vault_env_save.py --project mi-api --environment production \
  --variables '[{"name":"DATABASE_URL","description":"Conexión a PostgreSQL","sensitive":true}]'
```

---

## Grupo 9 — Migración

### `vault_migrate_docs.py`
Migra documentación externa al vault en 3 fases: staging → clasificación → distribución.

```bash
# Dry-run — ver plan sin ejecutar
python vault_migrate_docs.py --source_path "../docs" --project mi-api --dry_run true

# Ejecutar migración
python vault_migrate_docs.py --source_path "../docs" --project mi-api --dry_run false
```

---

### `vault_migrate_rollback.py`
Revierte una migración usando el reporte generado.

```bash
python vault_migrate_rollback.py \
  --report_path "10_Migrated/_report-mi-api-2026-05-09.md" \
  --confirm true
```

---

## Grupo 10 — Línea de Tiempo

### `vault_timeline.py`
Genera una vista cronológica de eventos del proyecto en `04_Sessions/`.

```bash
python vault_timeline.py --project mi-api
python vault_timeline.py --project mi-api --from "2026-05-01" --to "2026-05-09"
```

---

## Grupo 11 — Vista del Proyecto

### `vault_project_status.py`
Actualiza el estado actual del proyecto en `01_Projects/{project}/status.md`.

```bash
python vault_project_status.py --project mi-api --status active \
  --summary "Deploy v1.4 completado" --blockers "Pendiente review de seguridad"
```

---

### `vault_project_overview.py`
Genera o actualiza `01_Projects/{project}/overview.md` con stack, dependencias y decisiones.

```bash
python vault_project_overview.py --project mi-api \
  --description "API REST de pagos" --stack "Python,FastAPI,PostgreSQL"
```

---

## Grupo 12 — Código

### `vault_code_module.py`
Documenta un archivo de código en `11_Code/{project}/` (IEEE 1016 compliant). Genera classDiagram Mermaid automáticamente si se pasan `--classes`. Guard AP-17: consulta `.code-index.json` antes de crear; si `file_path` ya tiene entrada canónica, actualiza esa nota en lugar de crear un duplicado con slug diferente.

```bash
# Básico
python vault_code_module.py --project mi-api --file_path "src/server.py" \
  --description "Entry point del servidor" --language python

# Con exports (acepta JSON array o lista comma-separated)
python vault_code_module.py --project mi-api --file_path "src/auth.py" \
  --description "Auth service" --exports "login,logout,verify_token"

# Con métodos (IEEE 1016 Operations viewpoint)
python vault_code_module.py --project mi-api --file_path "src/auth.py" \
  --description "Auth service" --iso_type service \
  --methods '[{"name":"login","signature":"(str,str)->bool","description":"Autentica usuario"}]'

# Con clases (auto-genera classDiagram Mermaid)
python vault_code_module.py --project mi-api --file_path "src/models.py" \
  --description "Modelos de datos" \
  --classes '[{"name":"User","description":"Entidad usuario","extends":"BaseModel"}]'

# Escanear directorio completo
python vault_code_module.py --project mi-api --scan-path "src/"
```

| Parámetro | Descripción |
|---|---|
| `--project` | Slug del proyecto (requerido) |
| `--file_path` | Ruta real del archivo fuente (identificador canónico) |
| `--description` | Propósito del archivo (1-3 líneas) |
| `--language` | Lenguaje de programación |
| `--iso_type` | `module \| component \| service \| library \| script` |
| `--exports` | JSON array o lista comma-separada de símbolos exportados |
| `--imports` | JSON array de módulos importados |
| `--methods` | JSON array IEEE 1016: `[{name, signature, description, params, returns, raises}]` |
| `--classes` | JSON array IEEE 1016: `[{name, description, extends, properties, methods}]` |
| `--constants` | JSON array: `[{name, value, type, description}]` |
| `--exceptions` | JSON array: `[{name, raised_when}]` |
| `--quality` | JSON array ISO 25010: `[{attribute, rating(1-5), notes}]` |
| `--scan-path` | Directorio a escanear recursivamente |

---

### `vault_code_relation.py`
Registra una relación entre archivos de código y regenera `code-map.md`.

```bash
python vault_code_relation.py --project mi-api \
  --from_file "src/server.py" --to_file "src/core/models.py" \
  --relation_type imports --cardinality "1:1"
```

| `--relation_type` | |
|---|---|
| `imports`, `calls`, `uses`, `extends`, `implements`, `re-exports`, `depends_on` | |

---

### `vault_code_map.py`
Regenera `11_Code/{project}/code-map.md` desde `.code-index.json`.

```bash
python vault_code_map.py --project mi-api
```

---

### `vault_code_query.py`
Consulta el índice de código con filtros: por módulo, símbolo, lenguaje, relaciones. Retorna JSON sin leer los .md directamente.

```bash
python vault_code_query.py --project mi-api --symbol "login"
python vault_code_query.py --project mi-api --language python --iso_type service
python vault_code_query.py --project mi-api --file_path "src/auth.py"
python vault_code_query.py --project mi-api --relations "src/server.py"
```

---

## Grupo 13 — Backups

### `vault_backup.py`
Crea un snapshot completo del vault en `vault-backups/`.

```bash
python vault_backup.py
python vault_backup.py --label "pre-migration"
python vault_backup.py --label "antes-de-refactor-auth"
```

---

### `vault_backup_list.py`
Lista todos los backups registrados en `.backup-registry.json`.

```bash
python vault_backup_list.py
```

---

### `vault_restore.py`
Restaura el vault desde un backup específico.

```bash
python vault_restore.py --backup_name "vault-2026-05-09-143022-pre-migration" --confirm true
```

---

## Grupo 14 — Seguridad

### `vault_security_scan.py`
Escanea archivos de código en busca de 45 reglas de seguridad (OWASP/CWE). Guarda hallazgos en `02_Observability/vulnerabilities/`.

```bash
python vault_security_scan.py --path "src/" --project mi-api
python vault_security_scan.py --path "src/" --project mi-api --categories "secrets,injection"
python vault_security_scan.py --path "src/" --project mi-api --save_findings false
```

| `--categories` | Descripción |
|---|---|
| `secrets` | API keys, tokens, passwords hardcodeados |
| `injection` | SQL injection, command injection |
| `xss` | Cross-site scripting |
| `auth` | Problemas de autenticación |
| `crypto` | Algoritmos débiles |
| `all` (default) | Todas las categorías |

---

## Grupo 15 — Índices

### `vault_section_index.py`
Genera `{folder}/index.md` con lista de notas de una sección. Se llama automáticamente desde `vault_write`. Genera links como `[[nombre-nota]]` (sin path — AP-21 safe).

```bash
python vault_section_index.py --folder "01_Projects"
python vault_section_index.py --folder "02_Observability" --include_subdirs false
```

---

### `vault_master_index.py`
Genera `99_Index/index.md` con tabla resumen de todas las secciones del vault.

```bash
python vault_master_index.py
```

---

### `vault_reindex.py`
Reconstruye `search-index.json` desde cero. Herramienta de recuperación para índices vacíos o corruptos.

```bash
python vault_reindex.py
python vault_reindex.py --dry_run true        # ver qué se indexaría sin escribir
python vault_reindex.py --graph true          # también reconstruye graph.json
python vault_reindex.py --check               # solo verifica estado del índice
```

> Usar `--check` al inicio de cada sesión para verificar que el índice está operativo.

---

## Grupo 16 — Bibliografía

### `vault_bibliography_save.py`
Registra fuentes externas consultadas por el agente en `12_Bibliography/`.

```bash
python vault_bibliography_save.py \
  --title "Dining Philosophers Problem" \
  --url "https://en.wikipedia.org/wiki/Dining_philosophers_problem" \
  --summary "Problema clásico de concurrencia." \
  --source_type web --agent claude --tags "concurrency,deadlock"
```

| `--source_type` | Carpeta |
|---|---|
| `web` | `12_Bibliography/web/` |
| `paper` | `12_Bibliography/papers/` |
| `docs` | `12_Bibliography/docs/` |
| `api` | `12_Bibliography/apis/` |
| `book` | `12_Bibliography/books/` |

---

## Grupo 17 — Drift Detection

### `vault_drift_detect.py`
Detecta qué archivos del proyecto fueron modificados en la sesión y cuáles no tienen documentación en el vault. Soporta repos git y directorios sin git.

```bash
# Inicio de sesión — guardar baseline
python vault_drift_detect.py --path "." --project mi-api --mode snapshot

# Ver cambios sin análisis de vault
python vault_drift_detect.py --path "." --project mi-api --mode status

# Fin de sesión — reporte completo con cobertura
python vault_drift_detect.py --path "." --project mi-api --mode report
```

| Modo | Cuándo usar |
|---|---|
| `snapshot` | Primer comando al iniciar sesión |
| `status` | Ver cambios en cualquier momento |
| `report` | Último comando antes de cerrar sesión |

---

## Grupo 18 — Flujos

### `vault_flow_save.py`
Documenta flujos de trabajo, pipelines y ciclos de vida en `13_Flows/`.

```bash
python vault_flow_save.py --project mi-api --title "Flujo de Pago" \
  --flow_type workflow --content "# Flujo\n\n## Pasos\n1. Validar tarjeta..."
python vault_flow_save.py --project mi-api --title "CI/CD Pipeline" \
  --flow_type pipeline --content "..."
```

| `--flow_type` | Carpeta |
|---|---|
| `workflow` | `13_Flows/workflows/` |
| `pipeline` | `13_Flows/pipelines/` |
| `lifecycle` | `13_Flows/lifecycles/` |
| `dataflow` | `13_Flows/dataflows/` |

---

## Grupo 19 — Requerimientos

### `vault_requirement_save.py`
Documenta requerimientos funcionales y no funcionales en `14_Requirements/` (ISO 29148).

```bash
python vault_requirement_save.py --project mi-api --title "REQ-001 Auth" \
  --type functional --priority high \
  --content "El sistema debe autenticar usuarios via JWT con expiración de 24h."

python vault_requirement_save.py --project mi-api --title "REQ-NF-001 Latencia" \
  --type non_functional --priority medium \
  --content "El endpoint /api/payments debe responder en < 200ms en P99."
```

| `--type` | Descripción |
|---|---|
| `functional` | Comportamiento del sistema |
| `non_functional` | Calidad, rendimiento, seguridad |
| `constraint` | Restricciones técnicas o de negocio |

---

## Grupo 20 — Tests

### `vault_test_save.py`
Documenta casos de test en `15_Tests/` (ISO 29119).

```bash
python vault_test_save.py --project mi-api --title "TC-001 Login exitoso" \
  --test_type unit --status passed \
  --content "**Given** credenciales válidas\n**When** POST /login\n**Then** 200 + JWT"

python vault_test_save.py --project mi-api --title "TC-E2E-001 Flujo de pago" \
  --test_type e2e --status pending --content "..."
```

| `--test_type` | Carpeta |
|---|---|
| `unit` | `15_Tests/unit/` |
| `integration` | `15_Tests/integration/` |
| `e2e` | `15_Tests/e2e/` |
| `performance` | `15_Tests/performance/` |
| `security` | `15_Tests/security/` |
| `acceptance` | `15_Tests/acceptance/` |

---

## Grupo 21 — IA Governance

### `vault_ai_decision.py`
Registra decisiones tomadas por agentes IA en `16_AI_Governance/decisions/` (ISO 42001).

```bash
python vault_ai_decision.py --project mi-api \
  --title "Usar GPT-4 para clasificación de tickets" \
  --decision "Seleccionar GPT-4 sobre modelos locales por precisión" \
  --rationale "Benchmark interno: 94% vs 81% accuracy" \
  --agent claude --risk medium
```

| Parámetro | Descripción |
|---|---|
| `--title` | Título de la decisión |
| `--decision` | Qué se decidió |
| `--rationale` | Por qué se tomó la decisión |
| `--agent` | Agente que tomó la decisión |
| `--risk` | `low \| medium \| high` |
| `--alternatives` | Alternativas consideradas |

---

## Grupo 22 — Versionado del Estándar

### `vault_standard_upgrade.py`
Detecta la versión del estándar aplicada al vault y aplica migraciones pendientes (nuevas carpetas, actualizaciones de identity). Lee/escribe `00_System/standard-version.json`.

```bash
# Ver qué migraciones están pendientes (sin aplicar)
python vault_standard_upgrade.py --check

# Migrar desde v20 hasta v25
python vault_standard_upgrade.py --from v20 --to v25

# Aplicar todas las pendientes
python vault_standard_upgrade.py --to latest
```

**Migraciones disponibles:** v21, v22, v23, v24, v25

> Ejecutar `--check` al instalar el estándar en un vault existente para detectar brechas.

---

## Grupo 23 — Change Log

### `vault_change_log.py`
Registra el ciclo de vida de las notas: creadas, actualizadas, eliminadas, movidas. Escribe en `00_System/change-log.md` y `00_System/.change-log.json`.

**REGLA DE GOBERNANZA:** antes de eliminar cualquier nota del vault, llamar obligatoriamente:
```bash
python vault_change_log.py --action deleted --path <ruta> --reason <motivo>
```

```bash
# Registrar creación
python vault_change_log.py --action created \
  --path "01_Projects/mi-api/status.md" --reason "Sprint tracking inicial" --agent claude

# Registrar eliminación (REQUERIDO antes de borrar)
python vault_change_log.py --action deleted \
  --path "07_Knowledge/old-note.md" --reason "Duplicado de glossary/jwt.md"

# Registrar movimiento
python vault_change_log.py --action moved \
  --path "10_Migrated/draft.md" --new_path "07_Knowledge/jwt.md" --reason "Promovida"

# Consultar últimas 20 entradas
python vault_change_log.py --query --last 20

# Consultar por proyecto
python vault_change_log.py --query --project "mi-api" --last 10

# Consultar solo eliminaciones
python vault_change_log.py --query --action deleted
```

| Parámetro | Descripción |
|---|---|
| `--action` | `created \| updated \| deleted \| moved` |
| `--path` | Ruta relativa al vault de la nota afectada |
| `--reason` | Por qué se hizo el cambio (requerido). Alias: `--summary` |
| `--new_path` | Nueva ruta (requerido para `moved`) |
| `--agent` | Nombre del agente (default: `claude`) |
| `--query` | Modo consulta |
| `--last` | Número de entradas a retornar (default: 20) |

---

## Grupo 27 — Session Delta y Tags

### `vault_delta.py`
Detección de cambios entre sesiones via SHA-256 de contenido. Compara hashes actuales contra `99_Index/hash-index.json`, luego expande el conjunto cambiado via BFS sobre el grafo inverso de backlinks para encontrar notas transitivamente obsoletas.

```bash
python vault_delta.py --snapshot              # guardar baseline al inicio de sesión
python vault_delta.py                         # detectar cambios + actualizar hash-index
python vault_delta.py --dry-run               # detectar sin actualizar
python vault_delta.py --project mi-api        # acotar a un proyecto
python vault_delta.py --min-risk high         # solo stale_deps de riesgo high/critical
```

**Output:**
```json
{
  "ok": true,
  "changed": ["07_Knowledge/concepts/sqlite-schema.md"],
  "added": [],
  "deleted": [],
  "stale_deps": [{"path": "...", "distance": 1, "cia_integrity": "high", "stale_risk": 1.5, "via": "..."}],
  "summary": "1 modificada(s) · 2 dependencia(s) potencialmente obsoleta(s)"
}
```

### `vault_tags.py`
Registro canónico de tags. Construye y mantiene `00_System/tag-registry.json` escaneando todos los frontmatter. Detecta tags huérfanos, near-duplicados y notas sin tags. Genera `99_Index/tag-index.md` con backlinks por tag.

```bash
python vault_tags.py                          # rebuildar registry + tag-index.md
python vault_tags.py --audit                  # reporte de salud de tags
python vault_tags.py --suggest "01_Projects/mi-api/overview.md"
python vault_tags.py --rename "api-rest" "rest-api"
python vault_tags.py --dry-run
```

**Output `--audit`:**
```json
{
  "ok": true,
  "health_score": 87,
  "total_tags": 14,
  "orphaned_tags": ["unused-tag"],
  "near_duplicate_pairs": [{"tag_a": "sqlite", "tag_b": "sqlite3", "score": 0.85}],
  "singleton_tags": ["rare-tag"],
  "untagged_notes": ["01_Projects/mi-api/status.md"]
}
```

---

## Observabilidad de Tools

### `vault_errors.py`
Módulo de observabilidad centralizado. Todas las 59 tools lo importan. No es un tool de usuario — es la capa de seguridad del runtime.

**Funciones principales:**
- `wrap_main(fn, tool_name)` — envuelve `main()` con timeout (60s) y catch de excepciones no manejadas. Emite JSON estructurado en lugar de traceback.
- `emit_error(tool, code, message)` — construye error estructurado y lo registra en `00_System/.tool-trace.json`.
- `query_trace(tool, severity, category, last)` — para agentes que necesitan diagnóstico de fallos.

**Timeout:** configurable via `VAULT_TOOL_TIMEOUT` env var (segundos). Default: 60.

```bash
# Consultar últimas 10 entradas del trace log
python vault_errors.py query --last 10

# Filtrar por tool y severidad
python vault_errors.py query --tool vault_write --severity error

# Ver catálogo de errores
python vault_errors.py catalog

# Ver un error específico con su recovery hint
python vault_errors.py catalog --code AP21_PATH_WIKILINKS
```

**Estructura de error retornado:**
```json
{
  "ok": false,
  "tool": "vault_write",
  "error_code": "AP21_PATH_WIKILINKS",
  "category": "governance",
  "severity": "error",
  "message": "AP-21: wiki-links con ruta detectados.",
  "recovery": {
    "action": "fix_input",
    "hint": "Reemplazar [[carpeta/nota]] por [[nota]].",
    "docs": "vault-obsidian-architecture.md §AP-21"
  },
  "timestamp": "2026-05-09T00:00:00Z"
}
```

**Categorías de error:** `infrastructure`, `validation`, `governance`, `io`, `dependency`, `not_found`

---

## Grupo 24 — Data Quality

### `vault_quality_check.py`
Evalúa 9 dimensiones de calidad (integrity, consistency, completeness, accuracy, validity, timeliness, authenticity, non_repudiation, uniqueness) por nota y genera `00_System/quality-index.json`. Respeta umbrales CIA: notas `cia_integrity: critical/high` tienen límite de 15 días vs 30 días.

```bash
python vault_quality_check.py                     # score completo del vault
python vault_quality_check.py --min-score 0.7    # falla si score < 0.7
python vault_quality_check.py --folder 01_Projects/mi-api
```

### `vault_fundamentals.py`
Registro canónico de los 8 Fundamentos de Datos (F1–F8): INTEGRIDAD, CONSISTENCIA, COMPLETITUD, EXACTITUD, VALIDEZ, ACTUALIDAD, AUTENTICIDAD, NO_REPUDIO. Cada tool está mapeada a uno o más fundamentos.

```bash
python vault_fundamentals.py                      # lista F1–F8 con tools mapeadas
python vault_fundamentals.py --fundamental F1     # detalle de un fundamento
```

---

## Grupo 25 — Propagación

### `vault_impact.py`
Analiza el impacto de un cambio sobre el grafo de wiki-links usando BFS. Devuelve lista de notas afectadas por nivel de distancia.

```bash
python vault_impact.py --changed "01_Projects/api/overview.md"
python vault_impact.py --changed "overview.md" --depth 3
```

### `vault_propagate.py`
Propaga el impacto: marca notas afectadas como stale, las encola para revisión, o actualiza sus timestamps. Estrategias: `conservative` (solo directas), `aggressive` (todo el subgrafo).

```bash
python vault_propagate.py --changed "overview.md" --strategy conservative --action notify,queue
python vault_propagate.py --changed "overview.md" --strategy aggressive --action mark_stale
```

---

## Grupo 26 — Tokens

### `vault_tokens.py`
Cuenta tokens de notas usando la cadena: `anthropic` → `tiktoken` → heurística regex. Útil para estimar context window antes de inyectar notas al agente.

### `vault_token_counter.py`
Contador interactivo de tokens para un archivo o string dado.

### `vault_token_service.py`
Servicio de conteo de tokens con cache. Usado internamente por `wrap_main` cuando `VAULT_COUNT_TOKENS=1`.

**Funciones principales:**
- `wrap_main(fn, tool_name)` — envuelve `main()` con timeout (60s) y catch de excepciones no manejadas. Emite JSON estructurado en lugar de traceback.
- `emit_error(tool, code, message)` — construye error estructurado y lo registra en `00_System/.tool-trace.json`.
- `query_trace(tool, severity, category, last)` — para agentes que necesitan diagnóstico de fallos.

**Timeout:** configurable via `VAULT_TOOL_TIMEOUT` env var (segundos). Default: 60.

```bash
python vault_errors.py query --last 10
python vault_errors.py query --tool vault_write --severity error
python vault_errors.py catalog --code AP21_PATH_WIKILINKS
```

---

## Utilidades internas

Scripts de I/O y utilidades internas. No forman parte de los 26 grupos del estándar.

| Script | Descripción |
|---|---|
| `vault_io.py` | Primitivas atómicas: `atomic_write_text`, `atomic_write_json`, `file_lock`, `assert_within_vault` |
| `vault_index.py` | Actualiza `search-index.json` — llamado internamente por `vault_write` |
| `vault_dataset.py` | Extrae keywords con TF-IDF para búsqueda avanzada |
| `vault_link_safety.py` | Valida wiki-links antes de guardar (AP-21) |

---

## Deprecadas

Mantenidas solo para compatibilidad. Emiten `_deprecation` en la respuesta JSON. **No usar en nuevos proyectos.**

| Script | Reemplazado por |
|---|---|
| `vault_create.py` | `vault_write` (desde v21) |
| `vault_migrate.py` | `vault_migrate_docs` |
| `vault_reorganize.py` | `vault_migrate_docs` |
| `vault_tools.py` | Scripts individuales por grupo |
| `vault_render.py` | Obsidian Desktop renderiza nativo |

---

## Meta / Build

Tooling interno para generación y validación del estándar. No forman parte de la superficie de 53 tools.

| Script | Descripción |
|---|---|
| `vault_manifest.py` | Genera `00_System/tools-manifest.json` con metadata de las 66 tools |
| `vault_compact_contracts.py` | Genera `00_System/tool-contracts.md` compacto desde el spec |
| `vault_test_runner.py` | Suite de smoke tests, contract tests y error taxonomy tests |
| `vault_spec_memory.py` | Genera `00_System/spec-memory.json` — contratos + trazabilidad F1–F8 + estado DQ |

---

## Protocolo de sesión recomendado

```bash
# ── INICIO DE SESIÓN ──────────────────────────────────────────────
python vault_standard_upgrade.py --check           # 0. verificar versión del estándar
python vault_reindex.py --check                    # 1. verificar índice
python vault_validate.py --check structure         # 2. verificar estructura
python vault_audit.py                              # 3. baseline de salud
python vault_drift_detect.py --path "." --project {slug} --mode snapshot  # 4. baseline de cambios

# ── DURANTE LA SESIÓN ─────────────────────────────────────────────
# Toda escritura vía vault_write (nunca editar .md directamente)
# Antes de eliminar notas: vault_change_log --action deleted --path X --reason Y

# ── CIERRE DE SESIÓN ──────────────────────────────────────────────
python vault_drift_detect.py --path "." --project {slug} --mode report  # 5. cobertura
python vault_reindex.py --graph                    # 6. reconstruir índice + grafo
python vault_audit.py                              # 7. healthScore ≥ baseline
```

---

## Requisitos

- Python 3.9+
- Sin dependencias externas obligatorias (solo stdlib: `pathlib`, `json`, `hashlib`, `subprocess`, `uuid`, `datetime`, `threading`, `queue`)
- `nltk` opcional — solo para `vault_dataset.py` modo nlp (fallback a diccionario si no está instalado)
- Acceso de escritura al directorio vault

## VAULT_ROOT

Por defecto: `Path(__file__).parent.parent` — asume que `scripts/` está **dentro** del vault.

Si `scripts/` está **fuera** del vault (repo con vault como subdirectorio):
```python
# En cada script, cambiar:
VAULT_ROOT = Path(__file__).resolve().parent.parent / "vault-{nombre}"
```

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `VAULT_TOOL_TIMEOUT` | `60` | Segundos máximos de ejecución por tool antes de timeout |
