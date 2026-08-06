# Vault Scripts

Scripts Python del estándar **Vault Obsidian Architecture v39.0**. Implementan las 92 tools activas del vault como ejecutables CLI independientes + módulo de observabilidad + MCP server monolith.

- **112 archivos Python** — 92 tools del catálogo MCP (82 Python + 2 JS-native backup/restore base64) + 8 archivadas en `_archived/` + meta/spec + bibliotecas internas
- **AP-36 (v38.1, reforzado en v39)** — contención e idempotencia: todo side-effect (backups, traces, locks, stubs) vive DENTRO del vault; rutas derivadas de `get_vault_root()`, nunca de `__file__` ni CWD. `vault_norms.py --audit` lo verifica hasta **2 niveles** por encima del vault (el punto ciego del patrón `parent.parent.parent`) y reporta si la raíz se detectó por suposición
- **Contrato de tools (v39)** — `tool-spec.json` vive en **`<vault>/00_System/`**, resuelto por `vault_io.tool_spec_path()`. `resolve_tool_spec()` mantiene `scripts/tool-spec.json` como fallback de solo lectura para vaults no migrados
- **`VAULT_STRICT_ROOT` (v39)** — si la detección de raíz tendría que caer a la raíz del repo, lanza `RuntimeError` en vez de adivinar. Inspecciona la rama que resolvió con `vault_io.vault_root_origin()` / `vault_root_is_confident()`
- **Saneamiento de índices (v38.1)** — `vault_section_index.py --heal [--root]` regenera índices con formato legacy `[[stem|alias]]` o ausentes; el auto-index post-write se auto-cura si un agente escribe `index.md` a mano
- **MCP Server:** `../mcp/nodejs/vault-mcp-server.mjs` — monolito Node.js que expone las 92 tools via MCP Protocol (JSON-RPC 2.0) con transporte dual stdio + SSE/HTTP. Catálogo canónico generado desde `vault_mcp_catalog.py --sync`
- **Python 3.9+** requerido — sin dependencias externas obligatorias
- **VAULT_ROOT** auto-detectado por `vault_io.py` — soporta layouts consumer-repo (`scripts/` + `vault-foo/`) y scripts-inside-vault; requiere marcador de CONTENIDO (01_Projects/02_Observability/03_Decisions/.obsidian), no solo 00_System/99_Index (evita el ciclo auto-reforzado de detección); override runtime con `set_vault_root()`/env `VAULT_ROOT`
- **Timeout automático** — todas las tools terminan en ≤60s (configurable via `VAULT_TOOL_TIMEOUT` env var)
- **JSON siempre** — cualquier error devuelve `{"ok": false, "error_code": "...", "recovery": {...}}`
- **Frontmatter v29+** — todas las notas generadas incluyen `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`
- **Content gate estricto** — vault_write rechaza notas con <3 líneas reales y <10 palabras reales (AP-11 fuerte)
- **nextActions prescriptivo** — vault_audit devuelve un bloque `nextActions` con comandos copy-paste para mantener 100/100
- **Scaffolds auto-creados** — `vault_init` crea primers en secciones vacías para que el vault arranque en 100/100
- **Escrituras atómicas** — notas y JSON críticos usan `atomic_write_text`/`atomic_write_json` de `vault_io.py`
- **Convención de nomenclatura** — usa sufijos explícitos para eliminar ambigüedad: `-runtime`, `-config`, `-client`, `-db`, `-server`, `-service`, `-concept`, `-api`, `-framework`, `-pattern`, `-runbook`. Ej: `redis-runtime` (infra) vs `redis-client` (dependency) vs `redis-config` (config)

---

## Índice por grupo

| Grupo | Scripts |
|---|---|
| [Grupo 1 — Core](#grupo-1--core) | vault_write, vault_read, vault_search, vault_list, vault_append, vault_diff, vault_merge, vault_move |
| [Grupo 2 — Observabilidad](#grupo-2--observabilidad) | vault_log_error |
| [Grupo 3 — Patrones](#grupo-3--patrones) | vault_pattern_save, vault_pattern_list |
| [Grupo 4 — Diagramas](#grupo-4--diagramas) | vault_diagram_save, vault_relation_add, vault_mermaid_check, vault_diagram_export |
| [Grupo 5 — Conocimiento](#grupo-5--conocimiento) | vault_knowledge_save, vault_knowledge_get |
| [Grupo 6 — Salud del Vault](#grupo-6--salud-del-vault) | vault_audit, vault_validate, vault_graph, vault_graph_merge, vault_graph_inspect |
| [Grupo 7 — Runbooks](#grupo-7--runbooks) | vault_runbook_save, vault_runbook_log |
| [Grupo 8 — Infraestructura](#grupo-8--infraestructura) | vault_infra_save, vault_infra_map, vault_env_save, vault_env_matrix |
| [Grupo 9 — Migración](#grupo-9--migración) | vault_migrate_docs, vault_migrate_rollback |
| [Grupo 10 — Línea de Tiempo](#grupo-10--línea-de-tiempo) | vault_timeline |
| [Grupo 11 — Vista del Proyecto](#grupo-11--vista-del-proyecto) | vault_project_status, vault_project_overview |
| [Grupo 12 — Código](#grupo-12--código) | vault_code_module, vault_code_relation, vault_code_map, vault_code_query, vault_code_sync |
| [Grupo 13 — Backups](#grupo-13--backups) | vault_backup, vault_backup_list, vault_restore, vault_backup_base64, vault_restore_base64 |
| [Grupo 14 — Seguridad](#grupo-14--seguridad) | vault_security_scan |
| [Grupo 15 — Índices](#grupo-15--índices) | vault_section_index, vault_master_index, vault_reindex |
| [Grupo 16 — Bibliografía](#grupo-16--bibliografía) | vault_bibliography_save |
| [Grupo 17 — Drift Detection](#grupo-17--drift-detection) | vault_drift_detect |
| [Grupo 18 — Flujos](#grupo-18--flujos) | vault_flow_save |
| [Grupo 19 — Requerimientos](#grupo-19--requerimientos) | vault_requirement_save |
| [Grupo 20 — Tests](#grupo-20--tests) | vault_test_save |
| [Grupo 21 — IA Governance](#grupo-21--ia-governance) | vault_ai_decision |
| [Grupo 22 — Versionado](#grupo-22--versionado) | vault_standard_upgrade |
| [Grupo 23 — Change Log](#grupo-23--change-log) | vault_change_log |
| [Grupo 24 — Data Quality](#grupo-24--data-quality) | vault_quality_check, vault_fundamentals |
| [Grupo 25 — Propagación](#grupo-25--propagación) | vault_impact, vault_propagate |
| [Grupo 26 — Tokens](#grupo-26--tokens) | vault_tokens, vault_token_counter, vault_token_service |
| [Grupo 27 — Session Delta y Tags](#grupo-27--session-delta-y-tags) | vault_delta, vault_tags |
| [Grupo 28 — Producción/SRE](#grupo-28--producciónsre) | vault_incident_save, vault_slo_save |
| [Grupo 29 — Release](#grupo-29--release) | vault_release_save |
| [Grupo 30 — Riesgos/Calidad](#grupo-30--riesgoscalidad) | vault_risk_save, vault_privacy_save, vault_ncr_save |
| [Grupo 31 — Bootstrap](#grupo-31--bootstrap) | vault_init, vault_onboard |
| [Grupo 32 — Gestión de Carpetas](#grupo-32--gestión-de-carpetas) | vault_folder_registry |
| [Grupo 33 — Corrección Automática](#grupo-33--corrección-automática) | vault_fix_brackets, vault_graph_fix |
| [Grupo 34 — Memoria de Contexto](#grupo-34--memoria-de-contexto) | vault_preferences, vault_query_parse, vault_subgraph, vault_context_pack, vault_ingest |
| [Grupo 35 — Normas](#grupo-35--normas) | vault_norms, vault_arch, vault_code_tag, vault_doc_counts, vault_doc_sync, vault_noop_audit, vault_smoke, vault_voice |
| [Grupo 36 — Defectos y Cuarentena](#grupo-36--defectos-y-cuarentena) | vault_bug_save, vault_quarantine |
| [Grupo 37 — Skills](#grupo-37--skills) | vault_sdd_init, vault_sanacion |
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

**AP-41 — el ciclo de vida se verifica al escribir.** Al actualizar una nota
existente, `vault_write` lee su frontmatter y comprueba la transición de `status`
contra `vault_norms.STATUS_TRANSITIONS`. Una transición que no está en la máquina
se rechaza con `illegal_status_transition` y el mensaje enumera los destinos
válidos; si el salto era el correcto, lo que hay que corregir es la máquina, no la
nota. Consecuencias de la misma lectura: una escritura que **no** menciona
`status` conserva el estado previo (antes caía a `draft`), y el `id` y el
`createdAt` de la nota sobreviven a la actualización — el `id` que devuelve la
tool es el que está en el archivo.

```bash
# rechazado: desde 'draft' no se puede ir directo a 'verified'
python vault_write.py --folder "07_Knowledge" --title "N" --content "..." --meta '{"status":"verified"}'
# {"ok": false, "error_code": "illegal_status_transition", "from_status": "draft",
#  "to_status": "verified", "allowed": ["archived", "in-progress", "reviewed"]}
```

Las transiciones **ya ocurridas** no las ve el guard: las reporta
`python vault_norms.py --audit` recorriendo `.history/`.

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

### `vault_move.py`
Reubica una nota o una carpeta entera y **arrastra las referencias**: reescribe los wiki-links que apuntaban al origen, y regenera `search-index.json`, `graph.json` y el move-log. Mover un `.md` a mano rompe el grafo en silencio; esta tool es la forma soportada de hacerlo.

```bash
python vault_move.py --from "01_Projects/old/note.md" --to "03_Decisions/note.md"
python vault_move.py --folder "01_Projects/old" --to-folder "01_Projects/new"
python vault_move.py --from "01_Projects/foo.md" --to "03_Decisions/foo.md" --dry-run
python vault_move.py --impact --from "01_Projects/foo.md" --to "03_Decisions/foo.md"
```

`--impact` responde "¿a cuántas notas afecta esto?" sin tocar nada; `--dry-run` simula el movimiento completo.

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

## Grupo 4 — Diagramas

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

### `vault_mermaid_check.py`
Valida la sintaxis de los bloques Mermaid del vault antes de que Obsidian los renderice rotos. `--fix` intenta la corrección automática de los errores reversibles.

```bash
python vault_mermaid_check.py
python vault_mermaid_check.py --path "06_Diagrams/foo.md"
python vault_mermaid_check.py --project "mi-api"
python vault_mermaid_check.py --fix --json
```

---

### `vault_diagram_export.py`
Exporta diagramas con opciones de visualización persistidas (zoom, pan, dirección, nodos resaltados u ocultos). Sirve para sacar una vista concreta de un diagrama grande sin editar el original.

```bash
python vault_diagram_export.py --path "06_Diagrams/foo.md"
python vault_diagram_export.py --path "06_Diagrams/foo.md" --zoom 2.0 --pan_x 100
python vault_diagram_export.py --path "06_Diagrams/foo.md" --highlight "A,B" --hide "C"
python vault_diagram_export.py --project "mi-api" --filter flowchart --output "export/"
python vault_diagram_export.py --config --zoom 1.5 --fit   # guarda configuración global
```

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

### `vault_graph_merge.py`
Unifica en un solo grafo los tres tipos de relación que el vault mantiene por separado: wiki-links, relaciones de entidad y relaciones de código. Genera `99_Index/graph-enriched.json` con predicados semánticos resueltos contra `vault_ontology.json`.

Detecta tres anti-patrones de grafo: **AP-31** (grafo sin tipar), **AP-34** (relaciones tipadas huérfanas) y **AP-35** (silos de relación).

```bash
python vault_graph_merge.py
python vault_graph_merge.py --project "ans"
python vault_graph_merge.py --predicate-filter depends_on,implements,calls
```

---

### `vault_graph_inspect.py`
Inspector de grafo + detector de casi-duplicados + comprobador de sintaxis de wiki-links. Es la vista de diagnóstico previa a `vault_graph_fix`: dice qué está roto y por qué, sin escribir nada.

```bash
python vault_graph_inspect.py --root vault-sandbox
python vault_graph_inspect.py --md                  # informe legible en vez de JSON
python vault_graph_inspect.py --threshold 0.9       # umbral Jaccard de casi-duplicados
python vault_graph_inspect.py --no-templates        # excluye plantillas del near-dup
python vault_graph_inspect.py --include-migrated    # incluye 10_Migrated/ (excluida por defecto)
```

---

## Grupo 33 — Corrección Automática

Tool companion de `vault_audit`. Detecta y arregla automáticamente las pathologies de corchetes en wiki-links (`AP-22` empty `[[]]`, `AP-24` nested/inverted/imbalance) que el audit reporta en `issues.malformedWikilinks[]`. El auto-fix es seguro: solo toca las patologías reversibles y deja backup atómico en `VAULT_ROOT/.vault-fix-backup-YYYYMMDD-HHMMSS/` antes de modificar nada.

### `vault_fix_brackets.py`

Detecta y (opcionalmente) corrige brackets malformados en wiki-links.

```bash
# Dry-run: detecta y reporta qué arreglaría (default)
python vault_fix_brackets.py

# Aplica los auto-fixes seguros (con backup automático)
python vault_fix_brackets.py --apply

# Solo audita una nota o carpeta específica
python vault_fix_brackets.py --path "02_Observability/errors/foo.md"

# Solo corrige un tipo de pathology
python vault_fix_brackets.py --only empty --apply
python vault_fix_brackets.py --only nested --apply

# Incluye el sandbox de tests en el escaneo (default: excluido)
python vault_fix_brackets.py --include-sandbox
```

**Kinds detectados:**

| Kind | Norm | Auto-fixable | Qué hace |
|---|---|---|---|
| `empty` | AP-22 | ✅ | `[[]]` / `[[ ]]` → eliminado |
| `nested_open` | AP-24 | ✅ | `[[[[` → `[[` (colapsa anidados) |
| `nested_close` | AP-24 | ✅ | `]]]]` → `]]` (colapsa anidados) |
| `inverted` | AP-24 | ❌ | `]]…[[` orden invertido, requiere revisión manual |
| `unclosed_open` | AP-24 | ❌ | `[[` sin cerrar al EOF, requiere revisión manual |
| `inverted_resolvable` | AP-24 | ✅ | Stray closes que se resuelven al colapsar nested |
| `unclosed_open_resolvable` | AP-24 | ✅ | Opens sin cerrar que se resuelven al colapsar nested |

**Exclusiones automáticas:**
- `vault-obsidian-architecture.md` (el spec documenta la sintaxis `[[...]]`)
- `scripts/` (los tools contienen regex examples con brackets legítimos)
- `*.bak` (backups de upgrades)
- `vault-sandbox/` (test fixtures, requiere `--include-sandbox`)
- `.vault-fix-backup-*` (backups propios del fix)

**Garantías de seguridad:**
- Solo modifica notas dentro de `VAULT_ROOT` (path traversal bloqueado por `vault_io.assert_within_vault`)
- Backup atómico en `.vault-fix-backup-YYYYMMDD-HHMMSS/` antes de cada escritura
- Solo aplica cambios a notas marcadas como `auto_fixable: true` en el dry-run
- El kind `imbalance_*` NUNCA se auto-arregla — siempre requiere revisión manual

**Relación con `vault_audit`:** el bloque `nextActions` del audit ahora incluye `command: "python scripts/vault_fix_brackets.py --apply <path>"` para cada nota auto-fixeable, y `command: "Revisar <path>..."` para las que requieren revisión manual. El fix-tool y el audit comparten los mismos patrones de detección (`RE_EMPTY`, `RE_NESTED_*`, stack-based walk).

---

### `vault_graph_fix.py`
Repara wiki-links rotos. Clasifica cada enlace por confianza (`exact_candidate`, `points_to_migrated`, `partial_match`, `no_match`) y aplica solo lo que corresponde al modo elegido. Por defecto es **dry-run**.

```bash
python vault_graph_fix.py --root vault-sandbox --classify        # clasifica, no escribe
python vault_graph_fix.py --root vault-sandbox                   # dry-run del fix
python vault_graph_fix.py --root vault-sandbox --auto-fix-safe --apply
python vault_graph_fix.py --auto-apply-partial 0.75 --apply      # parciales de alta confianza
python vault_graph_fix.py --wizard                               # resuelve parciales a mano
python vault_graph_fix.py --stubs --apply                        # crea stubs para los no_match
```

`--auto-fix-safe` resuelve sin preguntar únicamente lo inequívoco. Los `partial_match` por debajo del umbral se **saltan y se registran**, nunca se adivinan: un enlace mal reparado es peor que uno roto, porque deja de reportarse.

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

### `vault_env_matrix.py`
Documenta la matriz de entornos de un proyecto (ISO 20000-1 / ISO 12207): qué servicios, feature flags, variables y procedimientos de deploy/rollback aplican en cada entorno. Genera `09_Infrastructure/{project}/matrix.md`.

Entornos: `dev`, `staging`, `prod`, `dr`, `perf`.

```bash
python vault_env_matrix.py --project my-api --env prod \
  --services '["api","postgres","redis"]' \
  --features '{"payments":true,"beta_ui":false}' \
  --env_vars '["DATABASE_URL","STRIPE_SECRET_KEY","JWT_SECRET"]' \
  --runtime "Node.js 20 LTS" --region "us-east-1"
```

`--env_vars` documenta **nombres**, nunca valores: un valor real ahí lo trata el escáner de secretos como incidente.

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

### `vault_code_sync.py`
Audita la trazabilidad bidireccional código ↔ vault: que cada nota con `source_file` apunte a un archivo que existe, y que ese archivo lleve su tag `@vault:`. Actualiza `11_Code/{project}/index.json`.

Estados por nota: `complete`, `missing_tag`, `missing_file`, `no_source_ref`, `orphan_vault`.

```bash
python vault_code_sync.py --project my-api
python vault_code_sync.py --project my-api --report      # salida legible
python vault_code_sync.py --scan-dir src/                # refs huérfanas en el código
python vault_code_sync.py --project my-api --fix --dry-run
python vault_code_sync.py --project my-api --fix         # inyecta @vault: donde falta
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

Las dos tools siguientes son las únicas **JS-native** del catálogo (sin entry point Python): viven en el servidor MCP y se invocan solo desde ahí. Están pensadas para mover un vault entre máquinas cuando no hay disco compartido ni remoto git. No sustituyen a `vault_backup`: no llevan manifiesto Merkle ni versionado incremental.

### `vault_backup_base64`
Serializa el vault entero a un `.b64zip.json` transportable por un canal de solo texto.

---

### `vault_restore_base64`
Restaura un `.b64zip.json` en un directorio nuevo. Nunca escribe sobre un vault existente.

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

## Grupo 22 — Versionado

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
python vault_tags.py --ledger                 # bitácora de vocabulario (AP-39)
python vault_tags.py --backfill-ledger        # heal AP-39: anotar lo ya en uso
python vault_tags.py --dry-run
```

**AP-39 — bitácora de vocabulario.** `vault_write` resuelve los tags contra el
registro **antes** de escribir (`apply_vocabulary`): colapsa lo que es la misma
palabra —acentos, mayúsculas, separadores, plural— y admite el término nuevo tal
cual. Una vez la nota está en disco, `record_new_tags` lo anota en
`19_Audits/vocabulary/tag-ledger.json`, append-only, con quién lo introdujo,
cuándo y en qué nota. `--backfill-ledger` retro-anota el vocabulario de un vault
anterior a la norma, usando el `agent` de la nota donde cada término aparece por
primera vez.

**Output `--ledger`:**
```json
{
  "ok": true,
  "introduced_total": 23,
  "canonical_total": 54,
  "by_agent": {"claude": 19, "unknown": 4},
  "entries": [
    {"tag": "kubernetes", "raw": "Kubernetes", "first_note": "07_Knowledge/k8s.md",
     "introduced_by": "claude", "introduced_at": "2026-07-29T09:10:38.000Z", "rule": "new"}
  ]
}
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
Módulo de observabilidad centralizado. Todas las tools lo importan. No es un tool de usuario — es la capa de seguridad del runtime.

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

Desde v39 es además la **fuente única del Marco de Datos y Gobernanza**: `CIA_TRIAD` (3), `FUNDAMENTALS` (8), `FAIR_PRINCIPLES` (4), `BIGDATA_VS` (6), `ISO_COVERAGE` (13) y `TRACEABILITY_MATRIX` (20 filas). La sección homónima del manifiesto se deriva de aquí y `vault_norms.py --check-framework` falla si divergen.

```bash
python vault_fundamentals.py                      # lista F1–F8 con tools mapeadas
python vault_fundamentals.py --fundamental F1     # detalle de un fundamento
python vault_fundamentals.py --framework          # exporta 00_System/data-framework.{json,md}
python vault_fundamentals.py --matrix             # matriz concepto → métrica → umbral → tool → enforcement
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

## Grupo 28 — Producción/SRE

### `vault_incident_save.py`
Registra incidentes y post-mortems (ISO 20000-1 / ISO 22301) en `02_Observability/incidents/`. Severidades `P1`–`P4`; el ciclo de estado va de `detected` a `closed` pasando por `post-mortem`.

```bash
python vault_incident_save.py --project my-api --title "API down" --severity P1

python vault_incident_save.py --project my-api \
  --title "DB latency spike" --severity P2 --status resolved \
  --detected_at "2026-06-01T14:30:00Z" --resolved_at "2026-06-01T16:45:00Z" \
  --impact "Checkout degradado 40% usuarios" \
  --root_cause "Index faltante tras migración" \
  --timeline '[{"time":"14:30","event":"Alert fired","who":"PagerDuty"}]' \
  --rto 30 --rpo 5
```

---

### `vault_slo_save.py`
Define SLOs de producción (ISO 20000-1 / ISO 25010) en `02_Observability/slos/`. Tipos: `availability`, `latency`, `error_rate`, `throughput`, `durability`, `freshness`, `saturation`.

```bash
python vault_slo_save.py --project my-api --service checkout \
  --slo_type availability --target 99.9 --window 30d

python vault_slo_save.py --project my-api --service api-gateway \
  --slo_type latency --target 200 --unit ms --percentile p95 \
  --window 7d --alert_threshold 300
```

---

## Grupo 29 — Release

### `vault_release_save.py`
Documenta releases de producción (ISO 20000-1 / ISO 12207) en `01_Projects/{project}/releases/`. Tipos `major|minor|patch|hotfix|rollback`; estados `planned|in_progress|deployed|rolled_back|cancelled`.

```bash
python vault_release_save.py --project my-api --version v1.2.0 --type minor \
  --changes '["feat: endpoint /health","fix: timeout checkout"]' \
  --deploy_steps '["npm run build","docker push","kubectl rollout"]' \
  --rollback_steps '["kubectl rollout undo"]' \
  --smoke_tests '["GET /health 200","GET /api/v1/products 200"]'
```

`rollback_steps` no es opcional en la práctica: una release sin vuelta atrás documentada es una release sin plan de contingencia.

---

## Grupo 30 — Riesgos/Calidad

### `vault_risk_save.py`
Registra riesgos (ISO 31000:2018 / ISO/IEC 27005:2022) en `01_Projects/{project}/risks/`. El nivel se calcula como `likelihood × impact`, ambos en escala 1–5.

| Producto | Nivel |
|---|---|
| 1–5 | Low |
| 6–12 | Medium |
| 13–19 | High |
| 20–25 | Critical |

```bash
python vault_risk_save.py --project my-api \
  --title "SQL injection en búsqueda" \
  --risk_type security --likelihood 3 --impact 5 \
  --treatment mitigate \
  --controls '["Parametrized queries","Input validation","WAF"]'
```

---

### `vault_privacy_save.py`
Inventario de tratamiento de datos PII (ISO 27701 / GDPR) en `02_Observability/privacy/`. `--purpose` y `--legal_basis` son obligatorios: un tratamiento sin finalidad ni base legal declaradas no es documentable, es un hallazgo.

```bash
python vault_privacy_save.py --project my-api \
  --title "Registro de usuarios" \
  --purpose "Autenticación y gestión de cuenta" \
  --legal_basis contract \
  --pii_categories '["name","email","phone"]' \
  --retention_period "24 meses tras baja" \
  --dpia_required false
```

---

### `vault_ncr_save.py`
Registra no conformidades y acciones correctivas (ISO 9001:2015 §10.2) en `02_Observability/ncr/`.

```bash
python vault_ncr_save.py --project my-api \
  --title "API no valida input en /search" \
  --ncr_type process --severity major \
  --detected_by code_review \
  --root_cause "Falta validación en la capa de entrada" \
  --corrective_actions '["Schema validation","Test de regresión"]' \
  --target_date 2026-08-15 --owner "equipo-api"
```

---

## Grupo 31 — Bootstrap

### `vault_init.py`
Levanta un vault vacío en un comando: crea las carpetas estándar, aplica las migraciones hasta la versión objetivo, indexa todo, genera las notas hub/commands y reporta el health score.

```bash
python vault_init.py                    # versión por defecto
python vault_init.py --target v39.0     # versión concreta del estándar
python vault_init.py --no-audit         # omite el vault_audit final
```

`--clean` **borra todo el contenido del vault actual** antes de inicializar (salvo `.locks`). No se ejecuta sin haber mirado antes qué hay en el destino.

### `vault_onboard.py`
Puebla un vault recién inicializado desde un **proyecto de código que nunca tuvo uno**. Lee el repo —estructura, manifiestos de dependencias, README, tests, scripts— y reconstruye su historia con git: detecta ramas snap/archive, contrasta la fecha del primer commit alcanzable contra la real y separa fases por tags en vez de por huecos en el calendario.

```bash
python vault_onboard.py --project mi-api --path ../mi-api
python vault_onboard.py --project mi-api --path ../mi-api --dry-run
python vault_onboard.py --project mi-api --path ../mi-api --skip 05 13
python vault_onboard.py --project mi-api --path ../mi-api --max-commits 5000
```

**Lee el proyecto, escribe solo en el vault.** El repo de origen no se toca.

Si el proyecto ya tenía documentación suelta, el orden es `vault_migrate_docs` **antes** que `vault_onboard`, para que el onboard no vuelva a escribir lo que ya estaba escrito.

Tres cosas que no hace, y son la parte que importa:

- **No escribe una nota sin evidencia detrás** (AP-45). Un módulo no merece nota por existir ni un commit por haber ocurrido. Lo que se queda fuera se reporta en `skipped_no_evidence`: un hueco nombrado se puede llenar, uno tapado con `_Pendiente_` ya no.
- **No se cree su propia salida** (AP-44). Relee cada nota del disco y valida el frontmatter con `yaml.safe_load`; los diagramas pasan por `vault_mermaid_check` y el que no valide no se escribe.
- **No puebla `18_Bugs`, `19_Audits` ni `20_Quarantine`.** Son secciones dirigidas por eventos: llenarlas al arrancar sería inventar bugs que no han pasado. La salida lo declara en `sections_left_empty_by_design` para que su vacío se lea como estado correcto y no como trabajo pendiente.

`--max-commits` acota la ventana de historia. Cuando se alcanza, la salida lo dice en `warnings`: el tope es un parámetro de la invocación, no un hecho del proyecto, y confundirlos convierte «500 commits» en un dato falso.

Criterio de aceptación, verificado en `tests/test_vault_onboard.py` contra un repo con git real: **un vault recién onboardeado no necesita sanación**. Cero deuda de metadatos, cero violaciones de norma, Mermaid limpio.

---

## Grupo 32 — Gestión de Carpetas

### `vault_folder_registry.py`
Registro de carpetas fuera de las estándar. Mantiene `00_System/custom-folders.json` para que una carpeta creada a mano no quede invisible para los índices, el audit y el grafo.

```bash
python vault_folder_registry.py --scan          # detecta carpetas nuevas
python vault_folder_registry.py --list
python vault_folder_registry.py --add "11_Code/tests"
python vault_folder_registry.py --remove "11_Code/tests"
python vault_folder_registry.py --cleanup       # quita del registro las que ya no existen
```

---

## Grupo 34 — Memoria de Contexto

Eje **consulta → contexto**. El resto del catálogo cubre el eje contrario
(escritura → gobernanza): sabe qué se decidió, qué se aprendió y qué pasó, pero
devolver *"lo que hay que saber para responder esto, en N tokens"* quedaba en
manos del agente, sin criterio ni traza.

Sin base de datos, sin embeddings y sin servicio externo: reglas léxicas sobre
los vocabularios que ya existen en el repo, más el grafo de wiki-links.

### `vault_preferences.py`
Preferencias del usuario como **contexto estable**: cómo quiere trabajar, qué no
debe tocarse. Viven en `17_Preferences/{workflow,style,tooling,constraints,domain}`,
separadas de `07_Knowledge` porque su ciclo de vida es distinto — una preferencia
se **revoca**, no se corrige. Fuerza normativa `must | should | may` (estilo RFC
2119) para que el agente distinga una restricción dura de una inclinación.

Revocar marca `status: revoked` con motivo y **no borra la nota**: sin ella se
pierde la explicación de por qué el agente se comportaba distinto antes.

```bash
python vault_preferences.py --set --category constraints \
    --title "No mover tools entre repos" \
    --statement "No propagar scripts a otros repos salvo petición explícita" \
    --strength must --agent mi-agente
python vault_preferences.py --list --strength must
python vault_preferences.py --context          # bloque listo para inyectar
python vault_preferences.py --revoke "17_Preferences/style/tabs.md" --reason "migró a prettier"
```

### `vault_query_parse.py`
Lenguaje natural → consulta estructurada: términos, frases, tags, semillas,
secciones, `status`, intención, profundidad y ventana temporal. **Determinista**:
misma frase, misma consulta, siempre. Cuando no está seguro no adivina — baja
`confidence` y deja el término a la búsqueda léxica.

```bash
python vault_query_parse.py "qué decidimos la semana pasada sobre MCP" --explain
python vault_query_parse.py "errores de ayer en [[mcp-protocol]]" --plan-only
```

### `vault_subgraph.py`
Subgrafo de **K semillas y N saltos**. A diferencia de `vault_impact` (solo hacia
atrás, pregunta fija), expande en la dirección que se le pida, pondera cada
arista por su predicado (un `wiki_link` explícito informa más que una
co-ocurrencia de tags) y decae la relevancia 0.6 por salto.

```bash
python vault_subgraph.py --seeds "03_Decisions/adr-001.md" --hops 2
python vault_subgraph.py --seeds a.md b.md --hops 3 --section 07_Knowledge
python vault_subgraph.py --seeds mcp-protocol --format mermaid
```

### `vault_context_pack.py`
Pregunta → contexto empaquetado bajo presupuesto de tokens. Encadena
`vault_query_parse` → `vault_search` → `vault_subgraph` → rerank → Top-K.

El rerank combina léxico (0.45), grafo (0.30), frescura (0.15, vida media 90d) y
CIA (0.10), con penalización para `deprecated`/`superseded`. Dos garantías:
el presupuesto **recorta notas enteras** —media nota es peor que ninguna, porque
el agente la cita como si estuviera completa— y las preferencias `must` entran
siempre primero.

```bash
python vault_context_pack.py "qué decidimos sobre el transporte MCP"
python vault_context_pack.py "errores del proyecto ans" --budget 2000
python vault_context_pack.py "auth" --format markdown --no-preferences
```

### `vault_ingest.py`
Ingesta gobernada de conversaciones, ficheros y URLs, con extracción determinista
de entidades (wikilinks, tags, rutas, siglas, nombres propios).

Es la vía por la que un vault se envenena, así que el **pre-vuelo anti-poison
(`cli.safety`) no es opcional ni desactivable**: si encuentra algo bloqueante no
se escribe nada. Además es **dry-run por defecto**, nunca sobrescribe una nota
existente, y lo ingerido entra con `status: draft` y `cia_integrity: low` hasta
que alguien lo revise. La red está apagada salvo `--allow-network` explícito.

```bash
python vault_ingest.py --file notas-reunion.md --section 07_Knowledge   # propuesta
python vault_ingest.py --file notas-reunion.md --section 07_Knowledge --commit
cat conversacion.txt | python vault_ingest.py --stdin --section 04_Sessions
```

---

## Utilidades internas

Scripts de I/O, encoding y utilidades internas. No forman parte de los grupos del estándar.

| Script | Descripción |
|---|---|
| `vault_io.py` | Primitivas atómicas: `atomic_write_text`, `atomic_write_json`, `file_lock`, `assert_within_vault` |
| `vault_encoding.py` | Normalización Unicode (NFC/NFD), sanitización de quotes/dashes/invisibles, detección BOM |
| `vault_regex.py` | Patrones regex para wiki-links, bracket detection, path-anchored validation |
| `vault_index.py` | Actualiza `search-index.json` — llamado internamente por `vault_write` |
| `vault_dataset.py` | Extrae keywords con TF-IDF para búsqueda avanzada |
| `vault_link_safety.py` | Valida wiki-links antes de guardar (AP-21) |
| `vault_errors.py` | Manejo de errores estructurado: wrap_main, emit_error, query_trace |
| `vault_errors_catalog.py` | Catálogo de códigos de error |
| `vault_errors_trace.py` | Trace logging + token counting |

---

## Archivadas (`_archived/`)

Scripts movidos a `_archived/`. No se usan en nuevos proyectos.

| Script | Motivo | Reemplazado por |
|---|---|---|
| `vault_create.py` | Deprecado (v21) | `vault_write` |
| `vault_migrate.py` | Deprecado (v25) | `vault_migrate_docs` |
| `vault_reorganize.py` | Deprecado (v25) | `vault_migrate_docs` |
| `vault_tools.py` | Deprecado (v22) | Scripts individuales por grupo |
| `vault_render.py` | Deprecado (v22) | `vault_diagram_save` |
| `vault.py` | Huérfano — CLI entry point temprano | Herramientas individuales |
| `vault_help.py` | Huérfano — sin referencias | Catálogo MCP |
| `vault_session.py` | Huérfano — sin referencias | `vault_session` (MCP) |

---

## Meta / Build

Tooling interno para generación y validación del estándar. No forman parte de la superficie de tools.

| Script | Descripción |
|---|---|
| `vault_manifest.py` | Genera `00_System/tools-manifest.json` con metadata de las tools |
| `vault_compact_contracts.py` | Genera `00_System/tool-contracts.md` compacto desde el spec |
| `vault_test_runner.py` | Suite de smoke tests, contract tests y error taxonomy tests |
| `vault_spec_memory.py` | Genera `00_System/spec-memory.json` — contratos + trazabilidad F1–F8 + estado DQ |
| `vault_sdd_init.py` | Inicializa documentación SDD (spec-driven documentation) |
| `vault_mcp_catalog.py` | Catálogo canónico de tools en Python — fuente de verdad. `--sync` exporta a JSON; `--check-contracts` verifica catálogo ↔ `tool-spec.json`; `--check-params` verifica catálogo ↔ `argparse` real (AP-40) |
| `vault_mcp.py` | Orquestador MCP en Python (alternativa al monolito Node.js) |
| `vault_mcp_context.py` | Generación de contexto MCP para agentes |

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
python vault_graph.py --typed                      # 7. enriquecer grafo con predicates semánticos (PAT-6)
python vault_audit.py                              # 8. healthScore ≥ baseline
```

---

---

## MCP Server Monolith (v39)

El vault expone sus herramientas como un **servidor MCP** que las IAs consumen directamente sin registro en harness.

**Archivo:** `../mcp/nodejs/vault-mcp-server.mjs` (~1650 líneas, cero dependencias npm)  
**Plan:** `../mcp/PLAN.md` — documento de evidencia con 8 fases de implementación
**Catálogo:** `../mcp/nodejs/tools-catalog.json` — generado desde `vault_mcp_catalog.py --sync` (92 tools)

Los parámetros que el catálogo publica **se derivan del `argparse` de cada script**,
no se escriben a mano: el servidor compone `--<param>` literal, así que un param
que la CLI no acepta es una tool que falla siempre (AP-40). `--check-params`
audita el JSON generado contra el `argparse` real y `--sync` lo repara.

```bash
python vault_mcp_catalog.py --check-params    # AP-40: params publicados vs argparse
python vault_mcp_catalog.py --sync            # heal
```

### Modos de uso

```bash
# Modo stdio (cliente MCP lanza como proceso hijo)
node mcp/nodejs/vault-mcp-server.mjs

# Modo servicio (IAs se conectan directamente a la URL)
node mcp/nodejs/vault-mcp-server.mjs --port 3000
# → http://localhost:3000/sse
```

### Capas del monolito

| Capa | Descripción |
|------|-------------|
| MCP Protocol | JSON-RPC 2.0 nativo (initialize, tools/list, tools/call, resources) |
| Tool Registry | 76 tools con inputSchema completo (catálogo canónico via tools-catalog.json) |
| JS-native backend | 10 tools rápidas en JS: vault_read, vault_list, vault_search, vault_graph, vault_graph_inspect, vault_tokens, vault_token_counter, vault_fundamentals, vault_backup_base64, vault_restore_base64 |
| Python backend | ~66 tools via `spawn("python", ["scripts/v_*.py", ...])` |
| Guard Chain | 10 validadores pre-escritura: secret scan, content gate, bracket balance, empty links, path-anchored, table brackets, referenced notes, Mermaid, tag completeness, agent completeness |
| Multi-tenant | 13 vaults auto-descubiertos, sesiones por vault via SSE/HTTP |
| Traceability | Log inmutable de mutaciones con UUID + timestamp + agent + diff |
| Observability | Health checks + DQ 9 dimensiones |

### Nuevos validadores (no existían en las tools Python)

1. **Table Bracket Validator:** detecta `[[` o `]]` incompletos en celdas de tablas markdown
2. **Referenced Notes Validator:** bloquea writes con wikilinks a notas inexistentes o stubs (diferente a ghost links: es bloqueante, no advisory)
3. **Note Has Content Validator:** verifica que una nota referenciada tiene contenido real (≥3 líneas, ≥10 palabras)

---

## Grupo 35 — Normas

### `vault_norms.py`

Registro canónico de las 61 normas del estándar (AP-XX anti-patrones, PAT-X patrones, SP-XX protocolo de sesión, CN-XX convenciones) y su enforcement. Fuente única de `STATUS_VOCAB` (12 valores).

```bash
python vault_norms.py                             # catálogo completo
python vault_norms.py --norm AP-36                # detalle de una norma
python vault_norms.py --audit --root vault-sandbox  # audita el vault contra las normas con guard/audit
python vault_norms.py --audit --strict            # igual, pero exit 1 si hay violaciones (gate de CI)
python vault_norms.py --check-framework           # guard anti-drift: el manifiesto documenta todos
                                                  # los ids del Marco de Datos (CIA-*, F1–F8, FAIR-*,
                                                  # V1–V6, ISO-*). Falla si registro y doc divergen.
```

`--check-framework` se ejecuta contra `vault-obsidian-architecture.md` (raíz del repo del estándar) o contra `--spec <ruta>`. Es deliberadamente independiente de `--audit`: los vaults consumidores no contienen el manifiesto y no deben fallar por ello.

### `vault_code_tag.py`
Aplica etiquetas al **código fuente**, no a las notas: `@norm` para vincular un archivo con una norma del estándar (o con una etiqueta propia), y `@vault:` para apuntar desde el código a la nota que lo documenta. Es el extremo del lado del código de la trazabilidad que `vault_code_sync` audita.

```bash
python vault_code_tag.py --define cr-0989 --name "Cola de prioridad" --description "FIFO con pesos"
python vault_code_tag.py --apply cr-0989 --file "src/services/colas.cs"
python vault_code_tag.py --apply AP-22 --file "scripts/vault_write.py"
python vault_code_tag.py --link-vault "11_Code/my-api/colas" --file "src/services/colas.cs"
python vault_code_tag.py --scan --file "src/services/colas.cs"
python vault_code_tag.py --list --prefix cr
```

---

### `vault_doc_counts.py`

Guard anti-drift de **cifras escritas a mano** en la documentación. Cada número que describe el estándar (cuántas tools activas hay, cuántas normas, cuántas secciones) es una mentira futura: se escribe una vez, deja de ser cierto en el commit siguiente y nadie lo nota. Esta tool invierte la relación — la cifra vive en el registro canónico y el documento se comprueba contra él.

Hechos vigilados: `tools_active`, `groups`, `norms_total`, `norms_ap`, `sections`, `scripts`, `tests`. Documentos vigilados: `README.md`, `CLAUDE.md`, `docs/SKILLS.md`, `scripts/README.md`, `vault-obsidian-architecture.md`.

```bash
python vault_doc_counts.py --list             # valores vivos derivados del registro
python vault_doc_counts.py --check            # reporta cada cifra que diverge
python vault_doc_counts.py --check --strict   # exit 1 si algo miente (gate de CI)
python vault_doc_counts.py --fix              # reescribe solo el número, no la frase
python vault_doc_counts.py --check --no-slow  # omite el conteo de tests (lanza pytest)
```

**El changelog y la tabla de versiones quedan fuera del escaneo.** "76 tools" dentro de la entrada de v37 es historia correcta, no drift; reescribirla sería derogar el registro histórico. Los patrones son deliberadamente específicos por el mismo motivo: `"N normas"` a secas también casa con "las 14 normas manuales eliminadas", que es otro hecho. Un patrón laxo produce falsos positivos y el guard acaba desactivado — que es como mueren los guards.

### `vault_doc_sync.py`

Guard anti-drift de **nombres**. `vault_doc_counts` vigila las cifras; esta vigila que la referencia de tools no se quede atrás del catálogo. Comprueba que toda tool tenga su sección `###`, que toda clave de `GROUPS` tenga su `## Grupo N`, y que el índice tenga exactamente una fila por sección con el ancla resuelta.

El síntoma que la originó, medido en v39: diecinueve tools sin sección propia en este mismo archivo, un índice con 30 filas para 37 grupos, y la fila "Grupo 34 — Gestión de Carpetas" apuntando a un ancla inexistente (la sección 34 real es Memoria de Contexto). Un enlace roto dentro del propio documento, estable durante versiones enteras, porque nada lo comprobaba.

```bash
python vault_doc_sync.py --check
python vault_doc_sync.py --check --strict   # exit 1 si el README se quedó atrás (gate de CI)
python vault_doc_sync.py --fix              # regenera la tabla de índice desde GROUPS
```

El encabezado de cada grupo usa la **clave literal de `GROUPS`**, no un título propio. Es deliberado: llegaron a convivir tres vocabularios de grupo (la etiqueta `group` de cada tool, la clave de `GROUPS` y el título del README) y ninguno fallaba al divergir. `--fix` regenera el índice pero **no escribe prosa**: una tool nueva sin sección se reporta, no se inventa.

---

### `vault_arch.py`

**El plano técnico del estándar.** Los 37 grupos de este README son una taxonomía para *encontrar* una tool; no son fronteras. `vault_arch` declara las que sí lo son: **nueve contextos acotados** y un shared kernel, cada uno con su lenguaje ubicuo, sus puertos publicados y lo que no cruza.

Siguiendo la regla 3 de `CLAUDE.md`, el plano no es un documento: es el registro `CONTEXTS` con guard. `docs/ARQUITECTURA.md` se **deriva** de él y un test falla si el fichero publicado se queda atrás (AP-47 aplicado al propio plano).

```bash
python vault_arch.py --check --strict     # exit 1 si se cruzó una frontera nueva
python vault_arch.py --map vault_backup   # -> durabilidad
python vault_arch.py --blueprint          # regenera docs/ARQUITECTURA.md
python vault_arch.py --freeze             # recongela scripts/arch-baseline.json
```

Vigila dos deudas distintas. **Fronteras cruzadas:** un módulo que importa el módulo de otro contexto en vez de su puerto. **AP-49 — vínculo resuelto en tiempo de import:** una asignación de nivel de módulo que deriva de `VAULT_ROOT`, que deja inerte la costura `set_vault_root()` y obliga a `cli/runner.py` a aislar cada tool en un subproceso.

El grafo se reconstruye **por AST en cada ejecución**, incluidos los imports diferidos dentro de funciones: un `import vault_norms` escondido en un `try:` cruza la frontera igual que uno de cabecera. Ambas deudas arrancan congeladas y **solo pueden encoger** — un guard que exigiera cero el primer día fallaría el primer día y se desactivaría. Lo que sí es puerta dura desde el principio es que **todo módulo en disco pertenezca a un contexto**: clasificar cuesta una línea, y un módulo que ningún registro reclama no lo echa en falta nadie.

---

### `vault_noop_audit.py`

**AP-37 — no-op silencioso.** Detecta tools con side effects declarados que no exponen ningún **indicador de trabajo**: un campo cuyo valor distinga "hice N cosas" de "no hice nada". `ok: true` a secas es una afirmación no falsable.

El síntoma que originó la norma: `vault_standard_upgrade --to latest` devolvía `{"ok": true}` habiendo aplicado cero migraciones, y el bug sobrevivió versiones enteras porque su respuesta era indistinguible de un éxito real.

```bash
python vault_noop_audit.py --check            # estado de la deuda AP-37
python vault_noop_audit.py --check --strict   # exit 1 si la deuda CRECIÓ (gate de CI)
python vault_noop_audit.py --freeze           # recongela scripts/noop-baseline.json
```

**Baseline, no guard duro.** Casi todas las tools con side effects nacieron sin indicador; un guard que falla en decenas de sitios se desactiva el primer día. El conteo vivo lo da `--check`, no este README. La baseline congela la deuda conocida y solo puede **encoger**: toda tool nueva nace conforme, y la que se corrige sale de la lista y ya no puede volver a entrar. Tras saldar deuda hay que ejecutar `--freeze` para que el gate no la readmita.

---

### `vault_smoke.py`

**AP-42 — tool publicada sin haberse ejecutado nunca.** `--help` demuestra que el `argparse` se construye. No demuestra que el módulo importe sus dependencias, ni que el ejemplo documentado sea aceptado por la CLI, ni que la salida sea el JSON que el contrato promete.

Ejecuta el `example` del catálogo de cada tool contra una **copia desechable** del vault de pruebas y exige tres cosas, deliberadamente pocas: que termine, que su salida sea JSON y que ese JSON tenga `ok`.

```bash
python vault_smoke.py --check              # barrido completo sobre el catálogo
python vault_smoke.py --check --strict     # exit 1 si la deuda CRECIÓ (gate de CI)
python vault_smoke.py --tool vault_write   # una sola tool
python vault_smoke.py --freeze             # recongela scripts/smoke-baseline.json
```

**Un `ok: false` bien formado aprueba.** El ejemplo apunta a rutas que el sandbox no tiene, y rechazarlas educadamente *es* el contrato. Lo que se persigue es el fallo mudo: el traceback, el stdout vacío, el cuelgue.

**La primera medición encontró 41 de 87 tools fallando** — 36 porque el ejemplo documentado usaba flags que la propia CLI rechazaba, que es AP-40 trasladado a la superficie de documentación, y el resto por contrato de salida o por comillas sin cerrar en el `example`. Todas quedaron corregidas, así que la baseline nació en **0** y la norma es un guard duro desde el primer día, sin deuda que readmitir.

Las tools sin invocación posible (un servicio HTTP que por diseño no retorna) se declaran en `SIN_SMOKE` **con su motivo**. Una exención silenciosa sería el mismo fallo que la norma persigue.

---

### `vault_voice.py`

**AP-43 — norma sin refuerzo en el punto de uso.** El catálogo de normas está completo, versionado y con guards, y aun así el agente que documenta el vault no lo tiene delante mientras trabaja: se entera de que una norma existe cuando la incumple, y solo si es una de las que previenen en vez de una de las que se limitan a detectar en un audit que puede no correrse nunca.

`vault_errors.wrap_main` —el único punto por el que ya pasa la salida de todas las tools— añade a cada resultado un bloque **`vault_says`** derivado de `NORM_CATALOG` y del estado real de esa llamada:

```json
"vault_says": {
  "moment": "wrote",
  "message": "Acabas de cambiar lo que soy. 4 notas en disco, y eso queda en mi historial. Recuerda AP-14 — Wiki-links rotos o vacíos: ...",
  "focus": "AP-14",
  "norms": ["AP-11 — ...", "AP-41 — ...", "..."],
  "next": "python scripts/vault_norms.py --audit"
}
```

Tres momentos, y el vault habla de lo que acaba de pasar, no de una regla abstracta:

| `moment` | Cuándo | Qué refuerza |
|---|---|---|
| `blocked` | una norma frenó la llamada | esa norma exacta, y que el rechazo *es* la norma funcionando |
| `wrote` | hubo escrituras (ledger AP-37) | cuántas notas cambiaron y qué mirar después |
| `read` | no cambió nada | una norma de la tool, rotando, con su señal de incumplimiento |

El foco **rota** entre las normas que gobiernan esa tool: repetir siempre la misma la vuelve invisible a la segunda semana.

```bash
python vault_voice.py --tool vault_write   # las 17 normas que gobiernan la escritura
python vault_voice.py --coverage           # normas que NINGUNA tool pronuncia
```

`VAULT_VOICE=0` silencia el bloque; `VAULT_VOICE=verbose` añade descripción, señal y prevención de cada norma. Un fallo de la voz nunca puede romper una tool: se traga y la tool responde igual.

**Por qué vive en `wrap_main` y no en cada tool.** Una capa de refuerzo que hubiera que invocar tool por tool sería exactamente el registro-que-nadie-consume que esta norma existe para evitar — el fallo característico de este repo. `--coverage` cierra el círculo por el otro lado: una norma sin `tools_enforcing` ni `tools_detecting` no se pronuncia jamás, y el audit la nombra.

---

## Grupo 36 — Defectos y Cuarentena

Las dos secciones que este grupo alimenta no salen de un diseño a priori: salen de medir 17 vaults reales en producción. Los agentes ya estaban escribiendo estas cosas; al no existir sección, las repartían entre `02_Observability`, `07_Knowledge` y carpetas inventadas sobre la marcha (`docs/`, `scripts/`, `certificates/`). **Una nota sin sitio no desaparece: aparece en cualquier sitio.**

### `vault_bug_save.py`

**El ciclo del defecto, entero y enlazado (`18_Bugs/`).** Un error es un *evento observado* —esto falló, aquí está el stack trace, y para eso está `02_Observability/errors`. Un bug es un *defecto que se persigue hasta cerrarlo*.

Sin sección propia, el ciclo se repartía en tres notas sin nada que las uniera: el síntoma en `02_Observability/errors`, la causa raíz en `07_Knowledge`, la corrección en `03_Decisions`. El juicio de que "este defecto lo causó aquella decisión" vivía en la cabeza de quien lo vio y se perdía al cerrar la sesión.

```bash
python vault_bug_save.py --project mi-api --title "Token numérico coercionado" \
    --symptom "El literal 0.5 llega al CSS como '0.5px' y el layout salta" \
    --status open --severity high --agent claude

python vault_bug_save.py --project mi-api --title "Coerción de unidades CSS" \
    --phase root-cause --symptom "..." --causes token-numeric-coercion --agent claude
```

- **`--phase` determina la subcarpeta** (`open/`, `root-causes/`, `fixed/`), así que el estado no puede mentir sobre dónde vive la nota: una nota `fixed` en `open/` es imposible por construcción.
- **`--causes` / `--caused-by` son aristas tipadas**, no un `related` genérico. Es la diferencia entre "estas dos notas se mencionan" y "esta explica aquella" — y solo la segunda permite navegar hacia atrás desde el síntoma hasta el origen.
- **Síntoma obligatorio**: un bug sin síntoma observable no es reproducible y no se puede cerrar.
- `cia_integrity: high` mientras el defecto siga abierto: un bug vivo compromete la integridad de lo que el vault documenta.

### `vault_quarantine.py`

**Retener sin borrar (`20_Quarantine/`).** Existe porque **la alternativa a retener no es limpiar: es borrar**. Una nota sin sección determinable, o que disparó el pre-vuelo anti-poisoning, o que puede ser duplicado de otra, tiene que salir del camino sin desaparecer. Sin un sitio donde ponerla, la única salida operativa es `rm` — y eso contradice la política de no-derogación del estándar.

```bash
python vault_quarantine.py --add "07_Knowledge/rara.md" \
    --reason "Sin frontmatter y origen desconocido" --category unclassified --agent claude

python vault_quarantine.py --list --category suspicious
python vault_quarantine.py --restore "20_Quarantine/unclassified/rara.md" --agent claude
```

Tres propiedades que la hacen segura:

- **La nota se mueve, no se copia.** Dos copias de una nota dudosa es peor que una: la que queda fuera se sigue leyendo como contexto válido.
- **El origen se guarda dos veces** — en el frontmatter de la nota y en el ledger append-only. Si el ledger se corrompe, la nota sigue sabiendo de dónde salió; una cuarentena de la que no se sale es una papelera con otro nombre.
- **La razón es obligatoria**, y restaurar sobre un origen ocupado falla en vez de sobrescribir.

`status` no se toca al retener: el estado de la nota no cambió por estar en cuarentena, y sobrescribirlo destruiría el dato que quizá haga falta para clasificarla.

---

## Grupo 37 — Skills

Una **skill** es una capacidad que un agente descubre e invoca por nombre, sin que nadie se la explique: vive en `.claude/skills/<nombre>/SKILL.md` y su entry point es un script de este directorio. Es la puerta por la que un agente entra al estándar.

Estaba fuera del catálogo. Cuatro versiones con la skill documentada en `docs/SKILLS.md`, con tests de contrato propios, y sin una sola entrada ni en `tools-catalog.json` ni en `00_System/tool-spec.json` — así que la capa MCP no la veía y `--check-contracts` no podía echarla en falta: la puerta verifica catálogo → contrato, y lo que no está en ninguno de los dos no lo echa en falta nadie. Es AP-42 —capacidad publicada sin contrato ejecutable— sobre el punto de entrada de los agentes.

### `vault_sdd_init.py`

**Genera la documentación SDD del vault: 14 documentos bilingües en `docs/sdd/`.** Principios, máquinas de estado, guía para autores de tools, guía para consumidores, catálogo de antipatrones, matriz de referencia, metodología, métricas y roadmap.

```bash
python vault_sdd_init.py --bilingual
python vault_sdd_init.py --check                  # puerta AP-47
python vault_sdd_init.py --bilingual --force
python vault_sdd_init.py --vault-root /ruta/al/vault --bilingual
```

- **`--check` es la puerta que faltaba.** El documento se genera derivando el rango de antipatrones de `NORM_CATALOG`, así que el fichero recién escrito nunca miente; lo que envejece es el de la ejecución anterior, que se commiteó y se quedó quieto mientras el registro crecía por debajo. Medido: `04-antipatterns.md` anunciaba `AP-01..AP-35` y el índice `AP-01..AP-25` con el registro en `AP-01..AP-47`. Un mes, tres releases, seis puertas en verde. Es AP-47 —artefacto derivado desfasado— aplicado a la documentación del propio estándar.
- **`--force` no pisa `gaps.md`.** De los 14, ese es el único declarado *manual fill*, y su preservación no depende del flag: `--force` levanta la idempotencia de lo generado, no el permiso para pisar lo escrito a mano. La restricción estaba publicada sin excepción; el código sí tenía la excepción, y un `--force` para refrescar el rango se llevó por delante 85 hallazgos redactados a mano.
- **Contención (AP-36):** toda escritura ocurre bajo `<vault-root>/docs/sdd/`. La skill es read-only sobre el resto del vault.

### `vault_sanacion.py`

**El plan de sanación de un vault preexistente, medido.** Devuelve las 12 fases de [`docs/MODO-AGENTICO-SANACION.md`](../docs/MODO-AGENTICO-SANACION.md) con un veredicto por fase —`applies`, `clean` o `unknown`— y la evidencia que lo sostiene.

```bash
python vault_sanacion.py
VAULT_ROOT=/ruta/al/vault-ajeno python vault_sanacion.py    # donde de verdad sirve
python vault_sanacion.py --phase 8
python vault_sanacion.py --strict                            # exit 1 si algo aplica
```

- **No escribe. Nunca.** Es la regla 2 del modo agéntico —el subagente propone, no escribe— aplicada a la tool que propone. Cada fase nombra la tool del estándar que sí escribe, con su guard y su entrada en `.change-log.json`. Una tool de diagnóstico con permiso de escritura es un segundo autor sin norma que lo gobierne.
- **`unknown` no es `clean`.** Una fase que no se pudo medir es una fase que sigues debiendo, y sale como tal en `phases_unknown`. El primer intento leía `issues.*` esperando cifras cuando son listas de hallazgos: siete fases quedaron en `unknown` sin que nada fallara, que es precisamente por qué `unknown` tiene que ser visible y no colapsarse a "no hay deuda".
- **El orden es el contrato**, no una preferencia de presentación: reubicar (7) después de arreglar enlaces (8) vuelve a romper cada enlace que acabas de reparar. Saber qué fases puedes saltarte es lo que hace que el orden sea seguro de seguir.
- **La fase 1 siempre aplica.** Ninguna medida puede confirmar que copiaste el vault antes de tocarlo, y dar la copia por hecha es el único fallo de este modo que no tiene vuelta atrás.
- **El criterio de encoding descarta la tipografía deliberada.** `vault_encoding.detect_issues` marca em-dash y comillas tipográficas, que en un vault bien escrito son texto correcto: contarlos daba 106 notas «afectadas» de 111, y una fase que siempre aplica es una fase que nadie lee. La fase 5 es mojibake y caracteres rotos, no normalización tipográfica.

Contrastada contra un vault ajeno al estándar (regla 7), en solo lectura: 232 notas, 199 violaciones de norma, 146 enlaces rotos, 4 secciones sin carpeta, `index_stale` con 311 en disco y 290 indexadas — y la fase 9 limpia. Que discrimine entre fases es la única prueba de que mide algo.

Referencia completa de la capa de skills —instalación, ciclo de vida, cómo añadir una— en [`docs/SKILLS.md`](../docs/SKILLS.md).

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
