# Vault Scripts

Scripts Python del estándar **Vault Obsidian Architecture v39.0**. Implementan las 103 tools activas del vault como ejecutables CLI independientes + módulo de observabilidad + MCP server monolith.

- **126 archivos Python** — 103 tools del catálogo MCP (82 Python + 2 JS-native backup/restore base64) + 8 archivadas en `_archived/` + meta/spec + bibliotecas internas
- **AP-36 (v38.1, reforzado en v39)** — contención e idempotencia: todo side-effect (backups, traces, locks, stubs) vive DENTRO del vault; rutas derivadas de `get_vault_root()`, nunca de `__file__` ni CWD. `vault_norms.py --audit` lo verifica hasta **2 niveles** por encima del vault (el punto ciego del patrón `parent.parent.parent`) y reporta si la raíz se detectó por suposición
- **Contrato de tools (v39)** — `tool-spec.json` vive en **`<vault>/00_System/`**, resuelto por `vault_io.tool_spec_path()`. `resolve_tool_spec()` mantiene `scripts/tool-spec.json` como fallback de solo lectura para vaults no migrados
- **`VAULT_STRICT_ROOT` (v39)** — si la detección de raíz tendría que caer a la raíz del repo, lanza `RuntimeError` en vez de adivinar. Inspecciona la rama que resolvió con `vault_io.vault_root_origin()` / `vault_root_is_confident()`
- **Saneamiento de índices (v38.1)** — `vault_section_index.py --heal [--root]` regenera índices con formato legacy `[[stem|alias]]` o ausentes; el auto-index post-write se auto-cura si un agente escribe `index.md` a mano
- **MCP Server:** `../mcp/nodejs/vault-mcp-server.mjs` — monolito Node.js que expone las 103 tools via MCP Protocol (JSON-RPC 2.0) con transporte dual stdio + SSE/HTTP. Catálogo canónico generado desde `vault_mcp_catalog.py --sync`
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
| [Grupo 6 — Salud del Vault](#grupo-6--salud-del-vault) | vault_fuente_unica, vault_audit, vault_validate, vault_graph, vault_graph_merge, vault_graph_inspect |
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
| [Grupo 33 — Corrección Automática](#grupo-33--corrección-automática) | vault_fix_brackets, vault_graph_fix, vault_frontmatter_heal |
| [Grupo 34 — Memoria de Contexto](#grupo-34--memoria-de-contexto) | vault_preferences, vault_query_parse, vault_subgraph, vault_context_pack, vault_ingest |
| [Grupo 35 — Normas](#grupo-35--normas) | vault_norms, vault_arch, vault_blame_audit, vault_changelog_check, vault_error_contract, vault_foreign_check, vault_gate, vault_code_tag, vault_doc_counts, vault_doc_sync, vault_noop_audit, vault_smoke, vault_voice, vault_servicio, vault_blueprint, vault_norms_coherence, vault_criterios |
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

#### Contexto acotado: Autoría (v40.0)

Los 38 módulos que escriben notas —`vault_write`, `vault_move`, `vault_read`, los 17
`*_save` y sus vecinos— forman el contexto **Autoría**, el último de los nueve en
migrarse al dominio. Al llegar aquí los otros ocho estaban a cero y Autoría concentraba
**los 31 vínculos congelados que quedaban: el 100% de la deuda de AP-49**.

La causa se ve en el diff, y no es un descuido puntual: veinticinco módulos derivaban
`SECCION_DIR = VAULT_ROOT / "0X_Loquesea"` en tiempo de import, cada uno copiado del
fichero de al lado al crearlo. `set_vault_root()` existía desde hacía versiones y no
podía reapuntar a ninguno — la costura de inyección estaba ahí y no servía.

Por eso `RepositorioAutoria` **no enumera secciones**: se piden por nombre a `seccion()`,
que valida contra `vault_registry.ORDERED_SECTIONS` y falla ruidosamente ante un nombre
desconocido. Veintidós constantes copiadas veinticinco veces eran veintidós ocasiones de
que un typo creara una carpeta huérfana en el vault del usuario sin que nada lo notara.

Cuatro rutas que Autoría lee y actualiza pero **no define** se piden a su dueño: el
índice de búsqueda, el de hashes y el registro de etiquetas a `RepositorioIndices`; el
grafo a `RepositorioGrafo`. `vault_change_log` pide la bitácora a `RepositorioGobernanza`,
que es quien la declara y de donde la leen `vault_fundamentals` y `vault_quality_check`.

Con esta fase `vault_arch --check` mide **0 vínculos congelados**, frente a los 82 en 62
módulos del arranque. Es la primera vez que la inyección de dependencias del estándar es
real en todo el dominio, y el test `test_no_queda_un_solo_vinculo_congelado_en_el_repo`
lo vuelve irreversible: cualquier módulo nuevo que derive su ruta al importarse lo rompe.

---

### `vault_read.py`
Lee una nota del vault por ruta relativa o por título.

```bash
python vault_read.py --path "01_Projects/mi-api/status.md"
```

---

### `vault_search.py`
Búsqueda full-text en `search-index.json` con score ponderado.

```bash
python vault_search.py --query "circuit breaker"
python vault_search.py --query "deploy" --tag proyecto/mi-api
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
python vault_pattern_save.py --project mi-api --name "Circuit Breaker" --type code \
  --description "Fallos en cascada" --notes "Solución y implementación"
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
python vault_pattern_list.py --type architecture
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

**El score sale del registro `PENALIZACIONES`, no de una fórmula escrita aquí.** Esta sección decía `100 - (vacías×2) - (sin_fm×3) - (broken_links×2) - (stale×1)` — cuatro términos de los veintidós que hay. Los pesos y los topes viven en el registro, agrupados por familia; copiarlos a la documentación es AP-05, y resumirlos mal es lo que ya pasó.

**`healthScore` satura, y se conserva igual.** Parte de 100 y resta 22 penalizaciones independientes cuyos topes suman **285**: con dos o tres familias mal se queda en 0 y deja de distinguir un vault regular de uno perdido. No es teórico — `vault-sandbox/`, el vault de referencia de este repo, puntúa 0. No se recalibra porque lo leen los repos consumidores y cambiar por debajo lo que significa un número publicado es peor que el número malo. Se anota `superseded_by: healthIndex` y se deja donde está.

**`healthIndex` y `healthProfile` son la lectura que sí discrimina.** Seis familias —estructura, conectividad, metadatos, grafo, contenido, ciclo de vida— cada una normalizada contra su propio tope. `healthIndex` es su media **simple**: ponderarla por tope dejaría que `metadatos` (105 puntos) decidiera el número, que es el defecto otra vez. Solo llega a 0 si todas las familias tocan fondo.

```jsonc
"healthScore": 0,          // satura: no dice nada más
"healthIndex": 60,
"healthProfile": {
  "conectividad": { "health": 27, "penalty": 51, "cap": 70, "saturated": false },
  "estructura":   { "health": 100, "penalty": 0, "cap": 30, "saturated": false }
  // …
},
"penalties": [ { "id": "orphans", "penalty": 26, "cap": 30, "norm_code": null } ]
```

`saturated` es la información que el número agregado destruía: dice qué familia ya tocó fondo, y por tanto dónde seguir empeorando ya no se nota.

| healthIndex | Estado |
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
python vault_graph.py --typed
```

Desde v40.0 las once tools del contexto **Grafo** resuelven sus rutas al usarlas, no al importarse: `99_Index/graph.json`, `graph-enriched.json`, `11_Code/.code-index.json`, el registro de etiquetas de código y los diagramas de entidad se declaran una sola vez en `vault/grafo/repositorio.py`. Antes eran dieciocho constantes congeladas repartidas entre once módulos, y solo once ubicaciones distintas: `GRAPH_FILE` se calculaba en tres ficheros y `CODE_DIR` en cinco (AP-05 + AP-49). El efecto visible es que `set_vault_root()` ya alcanza a estas tools.

En el mismo paso se corrigió que `vault_graph` devolviera `savedTo: "99_Index\graph.json"` en Windows mientras `vault_graph_merge` ya devolvía la forma POSIX — la misma ruta con dos formas dentro del mismo contexto, y la de Windows no la resuelve quien lee el envelope desde otra plataforma.

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

### `vault_frontmatter_heal.py`
Repara el frontmatter que **existe y no parsea** (AP-56). No es AP-28 —la nota sin bloque— sino la que abre `---`, se ve correcta al abrirla y para `yaml.safe_load` no tiene ni id ni tags ni estado. Por defecto es **dry-run**.

```bash
python vault_frontmatter_heal.py                  # mide, no escribe
python vault_frontmatter_heal.py --apply          # repara
python vault_frontmatter_heal.py --check --strict # exit 1 si queda algo ilegible
```

Dos causas, las dos mecánicas: **escalar sin escapar** (`title: Overview: demo` no es un mapeo) y **delimitador sin cerrar** (el bloque nunca cierra y el parser revienta cientos de líneas más abajo, dentro de un bloque de código — el mensaje de YAML señala dónde explotó, no dónde está el fallo).

Todo lo demás se reporta y **no se toca**: completar un YAML truncado inventa dato, que es peor que el hueco. Y una reparación se acepta solo si después `yaml.safe_load` devuelve un mapa y ninguna clave que ya se leía cambia de valor — el criterio del consumidor, no el propio (AP-44).

No acepta `--root` (regla 1): el destino sale de la autodetección o de `VAULT_ROOT`.

---

### `vault_fuente_unica.py`

**El mismo dato con valores distintos en varias notas (AP-05).** Puerta 16.

```bash
python vault_fuente_unica.py --check                 # los conflictos que hay
python vault_fuente_unica.py --report                # legible: qué valor dice cada nota
python vault_fuente_unica.py --check --strict        # exit 1 si hay conflictos nuevos (puerta 16)
python vault_fuente_unica.py --freeze                # baseline; solo puede encoger
python vault_fuente_unica.py --check --root <ajeno>  # contraste de la regla 7, solo lectura
```

**Por qué llegó en v40.15 y no en v19.** AP-05 es `critical` desde v19 y fue la última norma sin detector, declarada así en `cobertura_descubierta` en vez de escondida en una lista vacía. El motivo escrito era cierto: decidir qué es «el mismo dato» sin embeddings es un problema de diseño abierto.

Lo es **en general**. La observación que lo desbloquea es que no hay que resolverlo en general para medir lo que hace daño. Un dato **tipado** —IP, URL, puerto, semver— no se reconoce por parecido: se compara por igualdad. Y su identidad no hay que adivinarla, porque está escrita al lado en forma de clave. `host_ip: 10.10.10.45` en una nota y `host_ip: 10.10.10.50` en otra del mismo ámbito es AP-05 sin semántica de por medio.

| Qué se compara | Cómo se decide la identidad | Ámbito |
|---|---|---|
| `ipv4`, `url`, `puerto`, `semver` | la clave escrita al lado, en `clave: valor` | `project:` del frontmatter, o la carpeta de primer nivel |

**Lo que NO ve, dicho antes de que nadie se apoye en ello.** La divergencia **en prosa** («el servidor está en el .20») no lleva su clave escrita. Los valores **sin tipo** —un `status:`, un `owner:`— divergen entre notas legítimamente, y medirlos sería el ruido que hace que un guard deje de leerse. El **sinónimo** (`ip:` frente a `direccion_ip:`) es la misma cosa para una persona y dos claves distintas aquí; reconocerlo pedía justo los embeddings que el estándar no tiene. **Verde no prueba que el vault tenga una sola fuente de verdad**: prueba que no hay divergencia de la clase que se puede decidir sin interpretar.

**Las `CLAVES_DE_LA_NOTA` no son una exención.** Que dos notas tengan `version: 1.0.0` y `version: 2.0.0` no es que el dato diverja: es que son dos notas distintas. Sin esa lista la medida marca el frontmatter entero de cualquier vault y nace inservible.

**Lo que encontró en el contraste de la regla 7** —y no era reproducible en `vault-sandbox/`, que lo genera este repo—: dos conflictos reales en `/ans`, ambos en `09_Infrastructure/servers/`. `host_ip` valía `10.10.10.45` en `proxmox-01.md` y `10.10.10.50` en `proxmox-new.md`; `pve_version`, `9.1.1` en la primera y `8.4.16` en la segunda. Es exactamente el daño que la norma describe: un agente que lea la nota equivocada se conecta al host que no es. `/vcloud`, el vault de control, salió en cero.

Excluye instantáneas, documentación del estándar y bloques de código preguntando a sus dueños canónicos (AP-57) — un `ip: 10.9.9.9` dentro de un fence es un ejemplo, no una afirmación, y contarlo habría sido cometer AP-57 en la tool escrita para cumplirlo.

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
python vault_runbook_log.py --path "06_Runbooks/deploy/mi-api-deploy.md" \
  --outcome success --notes "Deploy v1.4.2 sin incidentes"
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
python vault_code_query.py --project mi-api --method "login"
python vault_code_query.py --project mi-api --class "AuthService"
python vault_code_query.py --project mi-api --file "src/auth.py"
python vault_code_query.py --project mi-api --deps "src/server.py"
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
python vault_backup.py --verify vault-2026-08-06-101500-pre-migration
```

Dos campos nuevos en v40.0, **aditivos**: ninguno de los anteriores cambia de nombre ni de significado.

- **`files_copied`** — el indicador de trabajo real (AP-37). `created`/`updated`/`written` salen de `vault_io.write_report()`, que solo ve lo que pasa por `atomic_write_text`; el snapshot se copia con `shutil`, así que un backup de 196 ficheros reportaba `written: 1`. Los viejos siguen significando lo mismo —cuántos ficheros escribió el kernel—; éste dice cuántos se copiaron.
- **`merkle_algo`** — la versión de la regla del hash, sellada en el manifiesto. `algo 2` excluye `00_System/.tool-trace.json` y `.voice-counter`, que cualquier ejecución reescribe y que hacían que dos copias de un vault intacto dieran raíz distinta: la medida arrastraba la huella de quien mide (AP-44). `--verify` usa **el algoritmo que diga el manifiesto**, no el vigente; un manifiesto sin sello es `algo 1` por definición, así que los backups anteriores se siguen comprobando con su regla y siguen dando íntegros.

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

Desde v40.0 el fichero es un **adaptador de transporte**: qué se borra, qué nunca se borra
(`vault-backups/`, `vault-sandbox/`) y de dónde se lee el snapshot viven en
`vault/durabilidad/restauracion.py`, con la raíz inyectada en vez de derivada al importar
(AP-49). El argv y el envelope no cambian; `files_restored` es el indicador de trabajo
(AP-37), junto al `noteCount` que ya declaraba. La ubicación legacy de backups —hermana del
repo, anterior a v38.1— se sigue consultando **solo para leer**, y se resuelve en el
adaptador porque es un detalle de despliegue, no una regla del dominio: por eso el error de
«no encontrado» enumera las dos rutas buscadas.

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
python vault_section_index.py --folder "02_Observability" --no-subdirs
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
python vault_reindex.py --dry-run             # ver qué se indexaría sin escribir
python vault_reindex.py --graph               # también reconstruye graph.json
python vault_reindex.py --check               # solo verifica estado del índice
```

> Usar `--check` al inicio de cada sesión para verificar que el índice está operativo.

Desde v40.0 las cuatro tools de este grupo son **adaptadores de transporte** del
contexto Índices (`vault/indices/`): argv y envelope intactos, pero la resolución
de rutas y el criterio de «qué es una nota indexable» viven en el dominio y
reciben la raíz en vez de derivarla al importar (AP-49). Ocho constantes
congeladas desaparecieron con la migración.

Dos consecuencias que se notan:

- **`--check` y la reconstrucción comparten enumerador** (`vault/indices/enumeracion.py`).
  No es una limpieza estética: si el check midiera con criterio propio, reportaría
  un desfase que el reindexado no cierra nunca y la puerta quedaría roja para
  siempre (AP-44).
- **Un vault colgado de un directorio con punto ya se indexa.** El filtro de
  tramos ocultos miraba la ruta *absoluta*, así que un vault en `~/.claude/`
  se reconstruía entero como vacío, sin error. Ahora el criterio es relativo al
  vault: se mide el vault, no la máquina que lo aloja.

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
python vault_flow_save.py --project mi-api --name "Flujo de Pago" \
  --type workflow --steps "Validar tarjeta" "Cobrar" "Confirmar"
python vault_flow_save.py --project mi-api --name "CI/CD Pipeline" \
  --type pipeline --steps "Build" "Test" "Deploy"
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
python vault_quality_check.py --path 01_Projects/mi-api
```

### `vault_fundamentals.py`
Registro canónico de los 8 Fundamentos de Datos (F1–F8): INTEGRIDAD, CONSISTENCIA, COMPLETITUD, EXACTITUD, VALIDEZ, ACTUALIDAD, AUTENTICIDAD, NO_REPUDIO. Cada tool está mapeada a uno o más fundamentos.

Desde v39 es además la **fuente única del Marco de Datos y Gobernanza**: `CIA_TRIAD` (3), `FUNDAMENTALS` (8), `FAIR_PRINCIPLES` (4), `BIGDATA_VS` (6), `ISO_COVERAGE` (13) y `TRACEABILITY_MATRIX` (20 filas). La sección homónima del manifiesto se deriva de aquí y `vault_norms.py --check-framework` falla si divergen.

```bash
python vault_fundamentals.py                      # lista F1–F8 con tools mapeadas
python vault_fundamentals.py --list               # detalle de cada fundamento
python vault_fundamentals.py --framework          # exporta 00_System/data-framework.{json,md}
python vault_fundamentals.py --matrix             # matriz concepto → métrica → umbral → tool → enforcement
```

---

## Grupo 25 — Propagación

### `vault_impact.py`
Analiza el impacto de un cambio sobre el grafo de wiki-links usando BFS. Devuelve lista de notas afectadas por nivel de distancia.

```bash
python vault_impact.py --changed "01_Projects/api/overview.md"
python vault_impact.py --changed "overview.md" --max-hops 3
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

Las secciones canónicas salen de `vault_registry`, nunca de una lista propia: la
copia literal que vivía aquí se quedó en 13 mientras el estándar ya tenía 22, y
las carpetas personalizadas de las nueve restantes eran invisibles sin que nada
fallara (AP-05 dentro del propio toolkit).

Desde v40.0 las rutas del registro salen del contexto Índices, y con la migración
se corrigió que `--scan` grabase `11_Code\tests` en Windows mientras `--add` y
`--remove` reciben `11_Code/tests`: una carpeta detectada automáticamente no se
podía quitar por su nombre, y el fichero no era portable entre plataformas.

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

**Qué cuesta una consulta (v40.7).** El recorrido es un BFS **sin conjunto de
visitados**: reencola un nodo cada vez que lo alcanza por un camino mejor, que es
lo que permite quedarse con la ruta más fuerte y no con la primera en un grafo con
ciclos —o sea, en cualquier vault real. Termina porque la relevancia decae: si
`peso * HOP_DECAY <= 1`, dar la vuelta a un ciclo nunca mejora lo ya visto. Ese
invariante estaba solo en la cabeza de quien escribió el bucle; ahora
`_check_hop_decay_invariant()` lo comprueba al importar y falla si un peso lo
rompe. Medido en un grafo de 60 nodos, contando encolados a 4/8/12 saltos: con
peso 1.6 (×0.6 = 0.96) el recorrido se queda plano en 59; con 1.7 (= 1.02) pasa a
125/365/605 y sigue creciendo. Subir un peso a 1.2 parece calibración y es un
cuelgue.

Con el invariante en pie, una consulta cuesta **O(V+E), independientemente de
`--hops`**. Y conviene leer bien qué acota `--max-nodes`: acota **la salida, no el
trabajo**. Medido sobre 500 nodos con grado 4 y con grado 8, a 2–6 saltos el BFS
encola 499 (= V−1) y devuelve 10. Bajar `--max-nodes` no abarata la consulta.

Se intentó arreglarlo con un mejor-primero (Dijkstra multiplicativo), que sí
permitiría parar en cuanto hubiera `max_nodes` nodos finalizados. **No es
equivalente, y se revirtió.** El motivo: aquí un nodo se expande cada vez que se
alcanza por un camino de más relevancia, y esas expansiones ocurren a
profundidades distintas —la más superficial conserva presupuesto de saltos y llega
donde la profunda ya no—. Un Dijkstra expande cada nodo una sola vez y pierde el
resto. Comparado envelope a envelope sobre 3.600 casos aleatorios (25 grafos × 3
densidades × 4 saltos × 4 topes × 3 filtros), cambiaban nodos y aristas; el
testigo fue una arista presente en un recorrido y ausente en el otro. Cambiar el
coste aquí es cambiar el envelope publicado, y eso no entra de refilón en un
arreglo de rendimiento.

`tests/test_bigo_grafo_y_recursion.py` fija las tres cosas —el invariante, el
coste real, y la expansión múltiple que hace inviable el atajo— para que un cambio
futuro no las desmienta en silencio.

Desde v40.0 el contexto **Consulta** resuelve sus rutas al usarlas: `17_Preferences/`, `00_System/token-usage/` y `.tool-tokens.json` se declaran una sola vez en `vault/consulta/repositorio.py`. Lo que **no** está ahí es el grafo — `99_Index/graph.json` lo escribe el contexto Grafo y `vault_subgraph` lo recibe de `RepositorioGrafo`, porque dos sitios decidiendo dónde vive el grafo es AP-05.

Ese cableado entre contextos ahora lo **ve** el guard: `vault_arch --check` reporta `vault_subgraph -> vault/grafo` como cruce declarado. Antes solo miraba los imports dentro de `vault/`, así que un adaptador podía cablear el dominio de otro contexto sin que saltara nada — el mismo punto ciego por el que se coló AP-48.

El caso más caro de AP-49 apareció aquí y no era una constante: `vault_compact_contracts` hacía `SYSTEM_DIR = _resolve_output_dir()`. Una llamada a función parece resolución tardía, el guard no la contaba, y se evaluaba igual al importar.

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

**El tope de tamaño es el mismo por las cuatro puertas** (`--max-chars`, por
defecto 5.000.000). Hasta v40.7 había tres topes distintos y uno inexistente:
`--text` estaba limitado a 200.000 caracteres por `safety.MAX_ARG_LENGTH` sobre
argv, `--url` a 5.000.000 escritos a mano en la llamada de red, y `--file` y
`--stdin` no tenían ninguno — es decir, las dos puertas cómodas eran las
descontroladas. El rechazo (`SOURCE_TOO_LARGE`) ocurre además **sin leer entero**
lo que se rechaza: se lee `tope + 1` y se decide.

```bash
python vault_ingest.py --file notas-reunion.md --section 07_Knowledge   # propuesta
python vault_ingest.py --file notas-reunion.md --section 07_Knowledge --commit
cat conversacion.txt | python vault_ingest.py --stdin --section 04_Sessions
python vault_ingest.py --file volcado.md --section 07_Knowledge --max-chars 200000
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

### Contexto acotado: Meta-toolkit (v40.0)

Los 13 módulos de este grupo —más `vault_smoke`, `vault_spec_*`, `vault_doc_counts`,
`vault_doc_sync`, `vault_noop_audit` y `vault_arch`— forman el contexto **Meta-toolkit**,
el único cuya frontera es una **prohibición** en vez de una interfaz. Al migrarlo se
saldaron 3 vínculos congelados (AP-49): 34 → 31.

**El enunciado que nadie comprobaba era falso.** `prohibe` decía «no escribir en un
vault» y ningún guard lo leía: solo se renderizaba en el plano. Medido, `vault_manifest`
escribe `00_System/tools-manifest.json` y `vault_spec_memory` escribe
`00_System/spec-memory.json` — y llevaban años haciéndolo. No es un abuso: son artefactos
derivados del propio estándar, y viven en el vault porque ahí es donde los consume un
agente. Lo que estaba mal era el enunciado, y un enunciado que el código incumple desde
el primer día es una norma con enforcement `manual` — lo que la regla 5 prohíbe.

La frontera precisa, y ya ejecutable en `vault_arch --check` (`forbidden_writes`):

- **Sí** artefactos derivados del estándar en `00_System/`.
- **Sí** vaults desechables para medirse: `vault_smoke` y `vault_test_runner` levantan
  un vault entero en un temporal y lo borran. Sin esa excepción la puerta se habría
  desactivado el primer día, que es como mueren los guards que solo saben decir que no.
- **No** notas ni datos del usuario en ninguna sección de contenido. Eso es lo que falla.

El guard busca por AST una llamada de escritura (`write_text`, `mkdir`, `atomic_write_*`…)
con el literal de una sección de contenido en su árbol de argumentos, y exime el destino
cuyo nombre traza —un salto— hasta `mkdtemp`/`TemporaryDirectory`. Por AST y no por texto
porque `vault_doc_counts` y el propio `vault_arch` **nombran** secciones en docstrings sin
escribir en ellas: un grep las delataría todas en falso (AP-44). Es puerta dura sin
baseline: se midió cero al declararla, y una lista de excepciones vacía solo invita a
estrenarla.

**Rutas ajenas.** `vault_spec_memory` derivaba por su cuenta `quality-index.json`,
`propagation-queue.json`, `.change-log.json` y `standard-version.json`, que **lee** pero
no escribe. Con eso `quality-index.json` llegaba a calcularse en cuatro módulos de tres
contextos: AP-05 multiplicado, y el día que se moviera solo se habrían enterado los que
lo escriben. Ahora se piden a `RepositorioGobernanza` y `RepositorioCicloDeVida`, y los
dos cruces están declarados en el baseline.

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
**Catálogo:** `../mcp/nodejs/tools-catalog.json` — generado desde `vault_mcp_catalog.py --sync` (103 tools)

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

Registro canónico de las 69 normas del estándar (AP-XX anti-patrones, PAT-X patrones, SP-XX protocolo de sesión, CN-XX convenciones) y su enforcement. Fuente única de `STATUS_VOCAB` (12 valores).

```bash
python vault_norms.py                             # catálogo completo
python vault_norms.py --show AP-36                # detalle de una norma
python vault_norms.py --audit --root vault-sandbox  # audita el vault contra las normas con guard/audit
python vault_norms.py --audit --strict            # igual, pero exit 1 si hay violaciones (gate de CI)
python vault_norms.py --check-framework           # guard anti-drift: el manifiesto documenta todos
                                                  # los ids del Marco de Datos (CIA-*, F1–F8, FAIR-*,
                                                  # V1–V6, ISO-*). Falla si registro y doc divergen.
python vault_norms.py --heal-ap46                 # informe en seco del frontmatter roto reparable
python vault_norms.py --heal-ap46 --apply-heal    # lo repara, con copia en <vault>/.history/ap46-heal/
```

`--check-framework` se ejecuta contra `vault-obsidian-architecture.md` (raíz del repo del estándar) o contra `--spec <ruta>`. Es deliberadamente independiente de `--audit`: los vaults consumidores no contienen el manifiesto y no deben fallar por ello.

#### `--heal-ap46` — reparar el frontmatter que dejaron los writers viejos

AP-46 prohíbe escribir frontmatter a mano, pero el guard llegó después que el material. `--heal-ap46` repara lo ya escrito, **en seco por defecto**: sin `--apply-heal` no toca un solo byte. La asimetría es deliberada — esta tool se ejecuta sobre vaults reales cuyo contenido no generó este repo, y reparar material ajeno sin que su dueño lo pida es justo lo que la regla 7 dice que no se hace. Con `--apply-heal`, cada nota se copia a `<vault>/.history/ap46-heal/<sello>/<ruta>` antes de reescribirse (AP-36: el side-effect vive dentro del vault).

Repara **dos clases y ninguna más**, las dos medidas sobre un vault ajeno al estándar:

| Clase | Rotura | Reparación |
|---|---|---|
| `escalar_sin_escapar` | `title: ADR-001: Adopción de MCP` — el segundo `:` abre un mapa donde había un escalar | reescapa con `yaml_scalar()`, solo las claves que el parser real no devuelve intactas |
| `bloque_sin_cerrar` | el `---` de apertura nunca cierra, así que el bloque entero se lee como cuerpo | cierra en el último renglón con forma de frontmatter |

Todo lo demás va a `skipped` con su motivo: el heal no adivina. Y **el cuerpo nunca se toca** — una propuesta que mueva un solo carácter por debajo del primer encabezado se descarta antes de escribirse.

La clase **no se deduce, se prueba**. Deducirla mirando si hay un `\n---` más abajo parecía obvio y clasificaba mal tres de las cuatro notas rotas del vault real, porque llevan una regla horizontal en el cuerpo: un bloque sin cerrar se leía como bloque cerrado que no parsea, y recibía la reparación equivocada. Ahora se construyen las dos propuestas y gana la que `yaml.safe_load` acepte. Es AP-44 aplicada dentro del propio heal: el criterio es el resultado que ve el consumidor, no la corazonada del detector.

Desde v40.0 el contexto **Gobernanza** —`vault_norms`, `vault_audit`, `vault_fundamentals`, `vault_quality_check`, `vault_drift_detect`, `vault_security_scan`, `vault_validate`, `vault_mermaid_check`— resuelve sus rutas al usarlas, declaradas una sola vez en `vault/gobernanza/repositorio.py`. Es el contexto con más acoplamiento entrante del estándar (veintisiete módulos de siete contextos importan `vault_norms`), así que era también el que más lejos propagaba una raíz mal congelada.

Siete vínculos los contaba el guard de AP-49; **ocho más no**, porque derivaban de los primeros sin nombrar `VAULT_ROOT` —`QUALITY_INDEX = SYSTEM_DIR / "quality-index.json"`— y se evaluaban en el mismo import, igual de inertes. Dos de esas ubicaciones se calculaban por duplicado: `quality-index.json` en `vault_audit` y en `vault_quality_check`, `.change-log.json` en `vault_fundamentals` y en `vault_quality_check`. Eso es AP-05 escondido dentro de AP-49, y ahora hay un test que lo fija.

La sustitución tuvo que hacerse **por AST y no por texto**: `vault_norms` cita `VAULT_ROOT` dentro de la descripción de AP-36 y de AP-49, y un reemplazo ciego habría reescrito el enunciado de las normas dejándolas ininteligibles sin que ningún guard se enterara. `test_gobernanza_dominio.py` comprueba que el texto del catálogo sigue nombrando `VAULT_ROOT` y no `_raiz()`.

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

### `vault_changelog_check.py`
El changelog del manifiesto, contrastado contra git. Cada entrada publica el commit
que introdujo su versión —`### v40.6 — 2026-08-07 \`git: bf8ba6d\``— y ese par
hash/fecha se escribía a mano sin que nada lo verificase.

Al medirlo por primera vez: **55 entradas, 31 con hash real, los 31 existen** —ninguno
inventado— **y 5 fechas contradecían al commit que citaban**. Cuatro por un día; la de
v39.0 por once, y esa entrada arrastra además un commit de fijado que corrigió el hash
(`13bf9ca -> 00731c6`) sin tocar la fecha. Las cinco se corrigieron, que es lo que el
propio preámbulo del changelog autoriza: la no-derogación prohíbe reescribir la
historia, no prohíbe que diga la verdad.

Comprueba cuatro cosas: que el hash exista y sea un commit, que la fecha coincida con
la de **autoría** del commit (`%as`, no `%cs` — un rebase reescribe la segunda y
estrenaría divergencias falsas), que ninguna versión ya cerrada siga publicando
`git: pending`, y que el orden sea decreciente. El guard del `pending` existía suelto
en la suite y solo cubría lo primero; además avisaba tarde, porque la excepción se
deriva de `CURRENT_VERSION` y no salta hasta la versión siguiente.

`--fijar-hash` resuelve el huevo y la gallina que originó todo esto: la entrada debe
citar el hash del commit que la contiene, y ese hash no existe hasta que el commit
está hecho. La salida era un ritual de dos commits —ocho veces en las últimas veinte
entradas del historial— cuyo segundo paso dependía de acordarse. Ahora es un comando,
que además toma la fecha del commit en vez de conservar la escrita a mano.

No commitea. Escribe el manifiesto y devuelve el mensaje de commit sugerido: una tool
de gobernanza que tocase el historial por su cuenta sería otra cosa distinta de un
guard.

```bash
python vault_changelog_check.py --check --strict     # la puerta `changelog`
python vault_changelog_check.py --list               # entradas + fecha real del commit
python vault_changelog_check.py --fijar-hash --dry-run
python vault_changelog_check.py --freeze             # solo para lo que no se pueda corregir
```

Un manifiesto en el que no reconoce ni una entrada devuelve `PARSE_FAILED`, no un
informe sin problemas. La distinción no es teórica: contrastado contra cinco copias
archivadas del manifiesto en un vault ajeno (regla 7), tres se leen enteras y dos
—migradas, sin la sección— caen por ese camino. Un guard que contara problemas y
nada más habría dicho «ok» sobre un fichero que no supo leer.

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

Desde v40.4 comprueba además una sexta cosa: que **todo comando `python scripts/X.py --flag` que la documentación publica exista y acepte esos flags**. Llegó tarde y con factura. `CLAUDE.md` publicaba, en su sección de comandos habituales, `vault_audit.py --root vault-sandbox` y `vault_quality_check.py --root vault-sandbox --min-score 0.7`: ninguna de las dos acepta `--root`, así que el comando que un agente copia para medir la salud del vault moría en `unrecognized arguments`. Lo contradecía la regla 1 del propio fichero —solo cuatro tools aceptan `--root`, el destino se fuerza con `VAULT_ROOT`— y duró versiones porque el manifiesto, el catálogo y los conteos tienen guard, y los comandos de la documentación no. Que el invisible fuese justo el de la salud es lo caro: nadie mide el vault a mano para descubrir que la herramienta de medirlo no arranca.

La comprobación es **estática** —los flags declarados en `add_argument`— y no ejecuta nada: varios de los comandos documentados escriben en el vault. Un parser construido donde el regex no llega daría un falso positivo, no un falso negativo; el guard se equivoca hacia el lado que se nota. El contraste lo pone `tests/test_comandos_publicados.py`, que sí ejecuta los dos comandos de salud tal y como están escritos en `CLAUDE.md`, leídos del documento y no copiados.

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

Se mide `scripts/` **y `vault/`**. Nació mirando solo el primero, con lo que el paquete que existe para imponer fronteras era el único que podía cruzarlas sin que saltara nada — pasaba por el guard de AP-49 y por ninguno más. En `vault/` la pertenencia la declara el directorio (`vault/<contexto>/`, sin registro paralelo: AP-05) y los imports relativos se resuelven a mano, porque `from ..gobernanza.x import y` cruza exactamente igual que `import vault_norms`.

Hay **una** excepción al límite 2, declarada por nombre en `RAIZ_COMPOSICION` y no escondida en el guard: `vault/kernel/adaptadores.py`, que cablea el `VaultContext` y por tanto tiene que conocer a todos. Lo que compra es que ese conocimiento viva en un fichero en vez de repartirse por el dominio; lo que cuesta es que ese fichero hay que leerlo entero al revisarlo.

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

### `vault_blame_audit.py`

**AP-51 — la tool culpa al dato de su propio fallo.** Detecta handlers amplios (`except Exception`, `except` desnudo) cuya única salida es un vacío indistinguible de un resultado legítimo: `return []`, `return {}`, `return None`, `pass`, `continue`.

El síntoma vino de ejecutar contra un vault **ajeno al estándar** (regla 7): tres tools declaraban inválidas notas que Obsidian leía sin problema. Las notas estaban bien; el criterio que las medía, no. AP-44 cubre la mitad de arriba —verificar con el criterio del consumidor—; esta cubre la de abajo, que es cómo un fallo propio acaba pareciendo un dato malo:

```python
try:
    fm = read_frontmatter(p) or {}
except Exception:
    return []          # <- el llamante lee "esta nota no tiene aliases"
```

El informe que agregue ese `[]` dirá que N notas carecen de aliases, y no será cierto: es que no se pudieron leer. **No es lo mismo "no hay" que "no pude mirar".**

```bash
python vault_blame_audit.py --check            # estado de la deuda AP-51
python vault_blame_audit.py --check --strict   # exit 1 si la deuda CRECIÓ (gate de CI)
python vault_blame_audit.py --freeze           # recongela scripts/blame-baseline.json
```

**Capturar amplio no infringe; capturar amplio y callarse, sí.** Devolver `ok: false` con el error es correcto: el llamante recibe la mala noticia y decide. Capturar `FileNotFoundError` tampoco infringe — es un criterio, el autor sabe qué tolera y por qué.

**Baseline, no guard duro,** por la misma razón que AP-37: la primera medición encontró deuda en decenas de módulos, y un guard que falla ahí se desactiva el primer día. El conteo vivo lo da `--check`, no este README. La clave de la baseline es el **sitio** y no un contador por módulo, porque una baseline por conteo se "salda" arreglando un sitio y estrenando otro — que es justo la regresión que este audit existe para ver.

Desde v40.6 ese sitio se identifica por **firma** (`módulo::función::hash del código normalizado`) y no por `módulo:línea`. El índice por línea convertía cualquier desplazamiento en deuda nueva: insertar diez líneas de comentario encima reportaba cuatro sitios nuevos y cuatro resueltos, y saldar deuda exigía verificar tres condiciones a mano antes de cada `--freeze`. Falló tres veces en una semana. El hash sale de `ast.unparse`, así que comentarios, sangrado y posición desaparecen antes de hashearse: mover un handler ya no lo reporta, cambiar su cuerpo sí. Ver `CLAUDE.md §Trabajar con las baselines`.

**Se mide por AST, no por texto,** y no es un detalle de implementación: un detector que buscara la cadena `except Exception` contaría los que están en comentarios y no distinguiría un handler que devuelve `[]` de uno que devuelve `ok: false`, que es toda la distinción que la norma sostiene. La primera versión del detector lo aprendió a su costa: midió 101 sitios porque clasificaba `except yaml.YAMLError` como captura amplia —son `ast.Attribute`, no `ast.Name`, y caían en la rama del `except` desnudo—, contando como infracción justo las capturas más precisas del repo. Quince falsos positivos, y el error era el de AP-44 cometido dentro del guard.

---

### `vault_error_contract.py`

**AP-52 — el error se emite fuera del contrato del catálogo.**

```bash
python vault_error_contract.py --check           # sitios fuera de contrato
python vault_error_contract.py --check --strict  # exit 1 si la deuda CRECIÓ
python vault_error_contract.py --freeze          # recongela tras saldar deuda
```

Salió de la caracterización maliciosa: invocar las 94 tools de forma malformada y mirar **cómo** fallan, no si fallan. El grueso estaba limpio —92/92 rechazan un flag desconocido, 45/45 de las que declaran `required_args` rechazan la invocación vacía— y el hallazgo estaba en la forma del envelope cuando fallaba bien:

```bash
$ python vault_merge.py
{"ok": false, "error": "action='merge' requires --source"}
```

La frase es correcta; el contrato, no. `emit_error` construye el envelope desde `ERROR_CATALOG` con `error_code`, `category`, `severity`, `recovery` y `timestamp`; el escrito a mano no trae ninguno de los cinco. Y el consumidor no lee la frase: **decide por el código**. El servidor MCP y `cli/` miran `error_code` y `recovery.action` para decidir si reintentan, abortan o piden permiso. Sin ellos, un fallo con recuperación conocida llega opaco, y lo único que le queda al agente es adivinar — o parsear el mensaje con un regex, atando su lógica a una cadena que nadie considera contrato.

Es AP-05 sobre el contrato de error, y AP-51 vista desde el otro lado: allí el fallo se disfrazaba de dato; aquí llega honestamente como fallo, pero desnudo de todo lo que lo hace accionable.

**Baseline: 158 sitios en 58 módulos al empezar, y solo puede encoger.** Misma razón que AP-37 —que empezó en 55 y llegó a 0— y que AP-51: un guard que falla en 158 sitios se desactiva el primer día.

**Deuda saldada en v40.6: la baseline está en cero**, y a partir de aquí el guard es duro — cualquier envelope de error nuevo construido a mano rompe la puerta. Los 110 sitios que quedaban tras las rondas anteriores cayeron en tres familias, y ninguna necesitó inventar nada: valor fuera de un vocabulario cerrado (`INVALID_VALUE`), JSON malformado en un argumento de la CLI (`ARG_JSON_INVALID`) y recurso que no existe (`FILE_NOT_FOUND`, `FOLDER_NOT_FOUND`, `NOTE_NOT_FOUND`, `INDEX_NOT_FOUND`). Los tres códigos nuevos existen porque forzar los que ya había daba un `recovery` equivocado: `JSON_PARSE_ERROR` recomienda `vault_reindex`, que no arregla un JSON que se escribió mal en la línea de comandos.

**Lo que no se convirtió, se declaró.** `EXENCIONES` lista los sitios que **tienen la forma** de un envelope de error de tool sin serlo: las filas del informe de `vault_smoke.run_one` —el dato que la tool produce cuando funciona, no su fallo— y los cuerpos de respuesta de `TokenHandler`, donde el contrato es el código de estado HTTP. Convertirlos habría roto al consumidor en nombre de cumplir la norma, que es peor que la deuda.

La exención se declara por `módulo::función` con motivo escrito, nunca por módulo entero. Eximir `vault_smoke` completo era más cómodo y se habría llevado por delante `vault_smoke.freeze`, cuyo `{"ok": False, …}` sí es el fallo de la tool. Hay tests que fijan las tres cosas: que ese sitio no esté exento, que cada exención siga apuntando a una función que existe —una exención muerta es una puerta abierta que nadie vigila— y que ninguna se declare sin motivo.

Donde el envelope llevaba claves útiles junto al error (`categories`, `fixes`, `suggestion`, `hint`, `path`, `detail`, `results`) se conservan **fuera** de `emit_error`, para no romper a quien ya las leía. Lo que cambia para el consumidor es que ahora hay `error_code` por donde decidir; lo que era `error: "invalid_folder"` —un código inventado en el sitio— pasa a `error_code: "INVALID_FOLDER"` del catálogo, con su `detail` intacto.

**Mide forma, no flujo.** Un `dict` con `ok: False` y pinta de envelope que no lleva `error_code`. No sigue el valor hasta stdout: eso exige análisis de flujo, y uno a medias produce falsos negativos silenciosos, que es peor que un falso positivo visible. La consecuencia se declara en vez de esconderse — algunos sitios contados son envelopes internos que nunca se imprimen. Están en la baseline, no bloquean, y quien salde su módulo los verá y decidirá.

---

### `vault_foreign_check.py`

**La regla 7, ejecutable.** Contrasta las medidas del estándar contra un vault **ajeno**, en solo lectura.

```bash
python vault_foreign_check.py --root "D:/vaults/notas"                    # el contraste
python vault_foreign_check.py --root "D:/vaults/notas" --report inf.json  # informe fuera del vault
python vault_foreign_check.py --self-test                                 # verifica sus negativas
```

**Es la única tool del estándar sin destino por defecto, y es deliberado.** Todas las demás autodetectan el vault y acaban en `vault-sandbox/`. Ésta no puede: `vault-sandbox/` lo genera este repo y comparte los supuestos de las medidas, así que un contraste contra él devuelve verde precisamente en el caso que existe para detectar. Sin `--root` falla diciendo qué le falta, y rechaza **cualquier** raíz dentro del repositorio.

**Solo lectura, sin excepciones.** Ni backups, ni índices, ni traces: el destino puede ser el vault de trabajo de alguien, y una tool de diagnóstico que modifica lo que diagnostica no es una tool de diagnóstico. El informe sale por stdout o al fichero de `--report`, que se rechaza si cae dentro del vault medido.

**Mide con el criterio del consumidor (AP-44):** el frontmatter con `yaml.safe_load`; los wikilinks por nombre de fichero y `aliases:`, nunca por `title:`, que Obsidian no mira; el texto probado contra cuatro encodings antes de declarar nada ilegible. Y todo recuento separa el cero medido del cero por fallo de lectura (AP-51) — un vault ajeno es justo donde esa distinción se cobra, porque la mayoría de los "defectos" que un estándar cree ver en material de fuera son su propio criterio fallando.

**No emite veredicto de salud, a propósito.** Un `score` invitaría a comparar vaults; lo que mide es si *nuestras* medidas sobreviven a material que no generamos. Una anomalía alta es antes sospechosa del criterio que del dato.

**El primer contraste real ya pagó la tool.** 317 notas de un vault consumidor: una con frontmatter que YAML no parsea. La causa no estaba en el vault sino en cómo el estándar escribe el título — siete sitios componían `title:` concatenando texto fuera de las comillas, y bastaba un `:` en un nombre de proyecto para romper el bloque entero (`vault_project_overview` lo rompía siempre: su título es literalmente `Overview: <proyecto>`). `vault-sandbox/` no podía exhibirlo, porque ninguno de sus nombres lleva `:`.

`--self-test` verifica las cuatro negativas sin necesitar un vault ajeno, y **no sustituye al contraste**: lo dice en su propio `hint`. La regla 7 solo se cumple ejecutando contra material de fuera.

---

### `vault_gate.py`

**La puerta única.** Corre todas las puertas de cierre y agrega el veredicto en un solo envelope.

```bash
python vault_gate.py            # corre todas
python vault_gate.py --strict   # exit 1 si alguna falla (gate de CI)
python vault_gate.py --list     # qué mide cada puerta y cómo se arregla
python vault_gate.py --check-doc  # el checklist de CLAUDE.md vs. el registro
```

El problema que resuelve no es de comodidad. Las puertas estaban repartidas en un checklist de prosa, y una lista en prosa falla de tres maneras que ya se cobraron su precio aquí: **nadie sabe cuántas son** —se decía "las siete" mientras el checklist tenía ocho ítems y la práctica corría seis—; **añadir una puerta no la pone en circulación**, porque un guard que nadie añade al checklist no corre, que es AP-42 aplicado a las propias puertas; y **correrlas a mano las corre a medias**, porque el comando que se saltea siempre es el más lento.

**La lista canónica vive en el registro `PUERTAS`, no en el doc,** y `--check-doc` verifica que el checklist de `CLAUDE.md` las cite todas. El orden es el del estándar —registro canónico primero, doc después, guard que falla si divergen—; al revés sería AP-50 estrenada en la misma versión que la declara. Si una puerta falta en el checklist, se añade al checklist: el registro manda.

**No reimplementa nada y no baja el enforcement de ninguna norma** (regla 5). Cada puerta corre como subproceso con su propio exit code y su propio envelope, y esta tool solo agrega. Mirar los datos por su cuenta la convertiría en una segunda fuente de verdad sobre el estado del repo (AP-05) y la haría medir con su criterio en vez del de la puerta (AP-44).

**No sustituye a `pytest`.** La suite es lenta y estas son rápidas: correrlas antes ahorra el ciclo largo cuando algo evidente está roto, pero verde aquí no es verde allí, y el envelope lo dice en su propio `hint` para que no haya que acordarse.

El campo `fix` de cada puerta distingue lo que se arregla solo —un artefacto derivado que solo hay que regenerar— de lo que exige decisión. Es lo que se lee cuando algo se pone en rojo a las once de la noche.

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

### `vault_servicio.py`

**El pilar.** Este repo tenía diez registros canónicos —`CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`, `GROUPS`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY`, el `tool-spec.json` y la tabla de entorno— y ninguno decía **para qué**. Se podía responder «esta tool, ¿en qué contexto vive?» y «esta norma, ¿qué severidad tiene?», pero no «esta tool, ¿a qué servicio sirve?». Sin esa respuesta una tool nueva no tiene contra qué justificarse, y el catálogo crece por acumulación.

Dos registros: `SERVICIO` —memoria documental persistente, auditable y gobernada para agentes LLM, sin base de datos, sin embeddings y sin servicio externo— y `CAPACIDADES`, que dice qué grupos del catálogo lo realizan. De aquí salen las capas 1 y 2 del plano de `vault_blueprint`.

```bash
python vault_servicio.py --list            # servicio, restricciones y capacidades
python vault_servicio.py --trace           # una fila por tool: grupo → capacidad → servicio
python vault_servicio.py --check --strict  # la trazabilidad, sin eslabón roto
```

**Trazabilidad exigida, que es lo que lo hace registro y no prosa:** todo grupo pertenece a exactamente una capacidad, ninguna capacidad reclama un grupo inexistente, ningún grupo está en dos, toda capacidad tiene al menos una tool viva y toda capacidad sirve a un servicio declarado. **Sin baseline**: se mide cero al declararla porque los 37 grupos se clasifican en la misma tanda, y una baseline aquí permitiría añadir un grupo sin decidir a qué sirve — justo el vacío que la tool cierra. Los `group_id` salen de `mapa_de_grupos()`; no hay una numeración propia.

**Por qué son tres capacidades y no dos.** `CLAUDE.md` declara dos ejes —*escritura → gobernanza* (grupos 1–33) y *consulta → contexto* (Grupo 34)—, y al clasificar los 37 grupos contra esa prosa aparecieron dos desajustes que no se pueden tapar sin mentir en el registro:

| Desajuste | Qué se midió |
|---|---|
| Grupo 35 (Normas, 14 tools) | Gobierna **el estándar**, no el vault de nadie: `vault_gate`, `vault_doc_sync`, `vault_arch`, `vault_changelog_check` y los tres audits con baseline no tocan una nota. Es una tercera capacidad, `gobernanza_del_estandar`, que existía desde la primera puerta y no tenía nombre |
| Grupo 26 (Tokens) | Cae en el rango 1–33 del primer eje, pero sus tres tools viven en el contexto `consulta` y existen para que el paquete de contexto quepa en la ventana. El rango es cronológico, no clasificatorio |

Forzar esas 17 tools al eje que no sirven habría sido el mismo fallo que la tool existe para evitar. El registro manda y la prosa se corrige.

---

### `vault_blueprint.py`

**El plano de construcción.** Once registros canónicos —`SERVICIO`, `CAPACIDADES`, `CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`, `GROUPS`/`TOOLS_CATALOG`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY` y el `tool-spec.json`— repartidos en diez módulos, y nada que los atara. Se podía responder cualquier pregunta *dentro* de un registro y ninguna que cruzara dos: «esta tool, ¿a qué servicio sirve?», «esta norma, ¿qué puerta la hace cumplir y qué test la muerde?».

```bash
python vault_blueprint.py --blueprint       # regenera docs/BLUEPRINT.md
python vault_blueprint.py --check --strict  # el plano vs. los registros (puerta 13)
python vault_blueprint.py --layers          # las 7 capas en JSON, sin escribir nada
python vault_blueprint.py --freeze          # congela la deuda de la capa 4
```

| Capa | Deriva de | Guard |
|---|---|---|
| 1 Servicio de negocio | `vault_servicio.SERVICIO` | — |
| 2 Capacidades → grupos | `CAPACIDADES` + `mapa_de_grupos()` | grupo huérfano = fallo |
| 3 Contextos → puertos | `vault_arch.CONTEXTS` | reusa `puertos_rotos()` |
| 4 Normas → puertas → tests | `NORM_CATALOG` + `PUERTAS` + `tests/` | **baseline que solo encoge** |
| 5 Tools → grupos → contrato | `TOOLS_CATALOG` + `tool-spec.json` | reusa `check_contracts()` |
| 6 Trazabilidad tool→capacidad→servicio | las anteriores | eslabón roto = fallo |
| 7 Deuda viva | `DEUDA_DECLARADA` + las baselines | informativa |

**El papelito manda porque lo escribe el código.** `docs/BLUEPRINT.md` es derivado y `--check` falla si diverge del registro: editarlo a mano no cambia nada y además rompe la puerta. Es la única forma de tener a la vez «fuente de verdad única en un documento» y la regla 3 —registro primero, doc después—, cuya nota advierte que documentar sin código ejecutable «es el fallo histórico que el estándar ya cometió una vez». Ni la deuda declarada se escapa: vive en el registro `DEUDA_DECLARADA` del módulo, porque una lista de deuda tecleada en un documento derivado se queda quieta el día que la deuda se salda, y entonces el plano miente en la dirección cómoda.

**Por qué solo la capa 4 tiene baseline.** Las otras seis se midieron en cero el día que se declararon: sus datos ya existían y solo faltaba atarlos. La capa 4 no — al cruzar `NORM_CATALOG` con `PUERTAS` y con `tests/` por primera vez aparecieron **16 normas sin puerta ni test**. Exigir cero el primer día habría hecho nacer la puerta en rojo, y una puerta en rojo se desactiva. `--freeze` se niega a congelar deuda sin precedente (`DEBT_WOULD_GROW`) salvo con `--admitir-nuevos`, que además la lista en el envelope.

**No reimplementa ningún guard.** Los puertos rotos los dice `vault_arch.puertos_rotos()`, los contratos `vault_mcp_catalog.check_contracts()` y la trazabilidad `vault_servicio.check()`. Un plano que midiera por su cuenta sería una segunda fuente de verdad sobre el repo (AP-05) midiendo con criterio propio (AP-44) — y `docs/ARQUITECTURA.md` no se absorbe: son dos documentos con dos sujetos, y fundirlos habría hecho uno solo que nadie regenera.

---

### `vault_norms_coherence.py`

**El catálogo de normas se certificaba a sí mismo (AP-55).** `NORM_CATALOG` declara, norma a norma, qué tools la hacen cumplir y cuáles la detectan. Los dos campos se escriben a mano y nada los cruzaba con lo que las tools hacen. Lo caro no era la lista: el guard que existía para detectar normas mudas —`vault_voice.coverage()`, el guard de AP-43— comprueba que una norma tenga `tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` y `tools_detecting`**. Verifica el catálogo contra el catálogo, así que daba verde sobre 47 afirmaciones que ningún módulo respalda y era estructuralmente incapaz de verlas. AP-44 cometido dentro del guard, por tercera vez en tres sitios distintos.

```bash
python vault_norms_coherence.py --check           # las cinco medidas
python vault_norms_coherence.py --check --strict  # exit 1 si algo falla (puerta 14)
python vault_norms_coherence.py --freeze          # recongela la baseline de C2
```

| Medida | Qué cruza | Estado al declararla |
|---|---|---|
| C1 enforcer resoluble | `tools_*` ↔ `mapa_de_grupos()` y `scripts/` | 54 valores corregidos → 0 |
| C2 la afirmación tiene traza | `tools_*` ↔ el código del módulo | 47, **baseline que solo encoge** |
| C3 enforcement ↔ campos | `enforcement` ↔ `tools_*` no vacíos | 0 |
| C4 severidad ↔ penalización | `severity` ↔ `vault_audit.PENALIZACIONES` | 1 (AP-22) → 0 |
| C5 distinción recíproca | `distinguido_de` ↔ `distinguido_de` | 0 |

**La traza no demuestra enforcement, y no se presenta como si lo hiciera.** `vault_write` podría rechazar AP-12 sin escribir nunca la cadena `"AP-12"`. Lo que C2 demuestra es lo contrario, que es lo verificable: si el código no nombra la norma en ninguna parte, nadie puede seguir la afirmación hasta el sitio que la cumple. Un guard que prometiera medir enforcement real sería justo la afirmación no falsable que AP-37 persigue. Las 47 se saldan de dos formas honestas —que el código nombre la norma donde la aplica, o que el catálogo retire la cobertura que no tiene—; ampliar la baseline es la tercera y no lo es.

**Lo que destapó C4.** AP-22 se declaraba `critical` mientras `vault_audit` la penalizaba con 2 puntos por unidad y tope 5, frente a los 5 y tope 15 de AP-24, que el catálogo llamaba `high`. Seis versiones con los dos registros invertidos. Manda el que se ejecuta (regla 3): AP-22 pasa a `medium`. El criterio se estrechó dos veces al medirlo — primero a la misma `familia` del healthIndex, después a exigir la inversión en **las dos** medidas del peso, porque AP-14 (`critical`, 2/unidad, tope 20) invierte una y no la otra y eso es una ponderación deliberada, no una contradicción.

**Lo que C5 no hace, dicho en voz alta.** No descubre por su cuenta qué dos normas se solapan. Tres borradores lo intentaron y los tres devolvían decenas de pares de `vault_audit` y `vault_write` consigo mismos: son los orquestadores y acumulan todas las normas del informe porque lo arman entero, no porque duden entre dos. C5 verifica la distinción **una vez que alguien la declara**, y exige que sea recíproca: si solo la declara A, quien llegue leyendo B no ve la diferencia. Los borradores quedan en el módulo sin llamar, como registro de lo intentado.

**Siete enforcers no son tools, y se admiten.** `vault_io.atomic_write_text` y `vault_io.assert_within_vault` son los helpers donde AP-46 y AP-36 se cumplen de verdad; `vault_errors` es donde vive el contrato de AP-43; `vault_mcp_catalog` es meta-toolkit que el catálogo MCP no se expone a sí mismo. Se verifican —módulo en `scripts/`, símbolo definido allí— y se publican aparte en `non_catalog_enforcers`. Obligarles a nombrar una tool solo conseguiría una afirmación que resuelve y es falsa.

### `vault_criterios.py`

**Un criterio con dueño, reimplementado en la medida (AP-57).** v40.12 arregló cuatro defectos de `vault_foreign_check` en una sola tanda, y los cuatro tenían la misma forma: **el registro canónico existía y la tool no lo consultaba**. Instantáneas congeladas contadas como notas; documentación del estándar contada como enlaces rotos; wikilinks dentro de un fence contados como enlaces; destinos con carpeta resueltos por basename. La regla 4 pide norma, no cuatro parches.

```bash
python vault_criterios.py --check                    # las copias que hay
python vault_criterios.py --check --strict           # exit 1 si hay copias nuevas (puerta 15)
python vault_criterios.py --freeze                   # baseline; solo puede encoger
python vault_criterios.py --freeze --admitir-nuevos  # congela deuda nueva, y la lista
```

| Criterio | Dueño | Cómo se consulta |
|---|---|---|
| qué es una instantánea congelada | `vault_io` | `is_snapshot_path` |
| qué es documentación del estándar | `vault_audit` | `es_documentacion_del_estandar` |
| qué es código y no un enlace | `vault_lib` | `strip_code_blocks` |

**No es AP-50.** AP-50 mira datos duplicados —vocabularios, defaults de entorno, patrones regex—: dos copias que divergen se ven al compararlas, porque hay algo que leer. Un criterio vive enterrado en un `if`, no hay dato que comparar, y la divergencia solo aparece por el resultado equivocado. El defecto de resolución por basename ponía la medida **verde** justo donde Obsidian pinta el enlace roto — 13 de 16 en el vault de control.

**Lo que encontró el primer día.** `vault_graph_fix` llevaba su propio `skip_set` de instantáneas, ya divergido de `vault_io.SNAPSHOT_DIRS`. Esa tool **escribe**: la divergencia no inflaba un número, reparaba dentro de una instantánea congelada, que es precisamente dejar de serlo.

**El límite, dicho antes de que nadie se apoye en él.** La detección es sintáctica: mira si un módulo que clasifica notas —los que escriben el literal `"*.md"`— reescribe la constante distintiva del dueño sin importar su símbolo. No hay forma general de decidir si dos funciones calculan lo mismo, así que un módulo puede reimplementar un criterio sin repetir ninguna constante y esta tool no lo verá. **Verde no significa que no haya copias**: significa que no hay copias de la forma que sabemos reconocer. Es lo que da un linter, y es preferible a no mirar.

La precondición del `"*.md"` no es cosmética: sin ella el detector marcaba a `vault_restore` por nombrar `vault-backups` —restaurar de ahí *es* su trabajo— y a `vault_norms` por nombrar el manifiesto, que edita. Un guard con ruido deja de leerse.

**Dos criterios con dueño que NO están en el registro, y por qué.** v40.14 promovió a `vault_lib` la resolución de un wikilink (`resolver_destino_wikilink`) y el índice de destinos que resuelven (`indice_de_destinos`). Registrarlos exigía darles señales, y las suyas serían `"|"`, `"#"` y `"aliases"` — que media docena de módulos escribe por motivos legítimos. El intento se hizo: **10 hallazgos nuevos, todos falsos.** Una señal que no distingue no es una señal, y congelarlos en la baseline habría sido comprar el verde con ruido, que es justo lo que la precondición del `"*.md"` existe para evitar. Tienen dueño y sus consumidores lo importan; lo que no tienen es forma sintáctica de vigilarlo. El límite está escrito en el docstring y fijado por un test, porque declararlo es más honesto que fingir una señal.

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

Desde v40.0 las tres propiedades son invariantes del contexto Durabilidad
(`vault/durabilidad/cuarentena.py`) y no código repetido en la tool. El parser de frontmatter
se **inyecta**: el dominio no sabe si detrás hay un regex o PyYAML, y eso es lo que permite
probar las reglas sin disco. El adaptador conserva argv, envelope y los caminos de error tal
cual estaban.

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

Desde v40.0 el contexto **Ciclo de vida** —`vault_init`, `vault_onboard`, `vault_standard_upgrade`, `vault_sanacion`, `vault_migrate_docs`, `vault_migrate_rollback`, `vault_propagate`, `vault_sdd_init`— resuelve sus rutas al usarlas, declaradas en `vault/ciclo_de_vida/repositorio.py`. Es el único contexto que corre **contra vaults ajenos por diseño**, y ahí congelar la raíz no produce un fallo ruidoso sino un informe verosímil del vault equivocado.

Que es exactamente lo que pasó: `vault_sanacion._medir_audit` reasignaba `vault_audit.VAULT_ROOT` para apuntar el audit al vault pedido. Al migrar Gobernanza esa constante dejó de existir, la asignación siguió siendo Python legal y dejó de hacer nada — las fases 2, 4 y 12 habrían medido el vault detectado, sin excepción que lo delatara. Ahora se apunta la raíz del proceso y **se devuelve en un `finally`**: read-only significa también no dejar rastro en el proceso de quien llama.

`propagation-queue.json` **no** se declara aquí: la escribe también `vault_audit`, es de Gobernanza, y `vault_propagate` la recibe de `RepositorioGobernanza`. Dos sitios decidiendo dónde vive un fichero es AP-05, y el cruce está declarado en la baseline de `vault_arch` para que se vea.

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
