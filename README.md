# Vault Obsidian Architecture

**Estándar de diseño para dotar a agentes LLM de memoria documental persistente.**

[![Version](https://img.shields.io/badge/version-v40.27-blue)](./vault-obsidian-architecture.md)
[![Tools](https://img.shields.io/badge/tools-106_active-green)](./scripts/)
[![Scripts](https://img.shields.io/badge/scripts-136_total-lightblue)](./scripts/)
[![Python](https://img.shields.io/badge/python-3.9+-yellow)](./scripts/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

---

## El problema

Los agentes LLM tienen memoria efímera. Cada sesión empieza desde cero aunque el proyecto lleve meses en desarrollo:

- Repiten errores ya resueltos
- No conocen el estado real del proyecto
- Las decisiones técnicas no tienen trazabilidad
- La infraestructura y reglas de negocio deben re-explicarse cada vez

**Este estándar resuelve eso** definiendo un vault de conocimiento que el agente lee, actualiza y navega como memoria persistente — sin bases de datos, sin embeddings, sin infraestructura adicional.

> El agente no necesita Obsidian instalado. Necesita el patrón y las tools.

---

## Qué es un vault

```
vault-{nombre}/          ← carpeta raíz (prefijo vault- obligatorio)
├── 00_System/           — identidad, reglas, contratos del agente
├── 01_Projects/         — overview, envs, estado por proyecto
├── 02_Observability/    — errores, vulnerabilidades, métricas, SLOs, maintenance/
├── 03_Decisions/        — ADRs y decisiones técnicas
├── 04_Sessions/         — bitácoras de sesión del agente
├── 05_Patterns/         — patrones con ciclo de vida evolutivo
├── 06_Diagrams/         — ERDs y diagramas Mermaid auto-generados
├── 07_Knowledge/        — glosario, APIs, conceptos, reglas de negocio
├── 08_Runbooks/         — procedimientos operacionales paso a paso
├── 09_Infrastructure/   — servidores, servicios, redes, pipelines CI/CD
├── 10_Migrated/         — documentación externa en tránsito
├── 11_Code/             — documentación de código IEEE 1016 por módulo
├── 12_Bibliography/     — fuentes externas consultadas por el agente
├── 13_Flows/            — flujos de trabajo, pipelines, ciclos de vida
├── 14_Requirements/     — requerimientos ISO 29148
├── 15_Tests/            — casos de test ISO 29119
├── 16_AI_Governance/    — decisiones de agentes IA (ISO 42001)
├── 17_Preferences/      — contexto estable del usuario (workflow, style, tooling…)
├── 18_Bugs/             — defectos con ciclo propio: open → root-causes → fixed
├── 19_Audits/           — bitácora del vault: auditorías y vocabulario introducido
├── 20_Quarantine/       — notas retenidas sin destino seguro (nunca borradas)
└── 99_Index/            — search-index.json, graph.json
```

Formato: **Markdown + YAML frontmatter + wiki-links**. Compatible con git, abre en cualquier editor, renderable en Obsidian Desktop.

---

## Garantías de datos

Un vault no es una carpeta de notas: es un activo de datos con garantías medibles.
Cada una tiene una métrica, una tool que la calcula y un artefacto donde queda escrita.
Detalle completo en [Marco de Datos y Gobernanza](./vault-obsidian-architecture.md#marco-de-datos-y-gobernanza).

| Eje | Qué garantiza | Dónde se mide |
|---|---|---|
| **Tríada CIA** (pilar) | Confidencialidad, Integridad, Disponibilidad como campos de frontmatter que **cambian el comportamiento de las tools**, no como etiquetas | `cia_sensitivity` / `cia_integrity` / `cia_availability` |
| **8 Fundamentos (F1–F8)** | Integridad, consistencia, completitud, exactitud, validez, actualidad, autenticidad, no-repudio | `vault_fundamentals`, `00_System/data-fundamentals.json` |
| **9 dimensiones DQ** | Los 8 fundamentos + unicidad, escala 0.0–1.0, umbral 0.7 | `vault_quality_check`, `00_System/quality-index.json` |
| **Principios FAIR** | Findable, Accessible, Interoperable, Reusable — con el mecanismo concreto que ya los cumple | `vault_search`, `vault_master_index`, `.history/` |
| **V's del Big Data** | Volumen, velocidad, variedad, veracidad, valor, variabilidad — cada V apunta a un número real | `vault_audit`, `vault_change_log`, `vault_delta` |
| **Trazabilidad** | Cadena verificable `agent:` → `.change-log.json` → `.tool-trace.json` → `.history/` → manifiesto Merkle | `vault_audit --trace` |
| **Gobernanza** | 73 normas AP/PAT/SP/CN, 0 con enforcement manual | `vault_norms --audit` |
| **Alineación ISO** | 13 normas mapeadas cláusula → implementación → tool | `vault_fundamentals --framework` |

```bash
python scripts/vault_fundamentals.py --framework   # exporta el marco completo (JSON + MD)
python scripts/vault_fundamentals.py --matrix      # matriz concepto → métrica → tool → enforcement
python scripts/vault_norms.py --check-framework    # guard anti-drift registro ↔ manifiesto
```

---

## Novedades v39.0 — Marco de Datos y Gobernanza explícito

- **Sección nueva en el manifiesto**: CIA, F1–F8, 9 dimensiones DQ, FAIR, V's del Big Data,
  estados, versionado en tres planos, trazabilidad, gobernanza, cobertura ISO y matriz de
  trazabilidad de 20 filas — todo con métrica, umbral, tool y artefacto.
- **Registro canónico ejecutable** en `scripts/vault_fundamentals.py` (`CIA_TRIAD`,
  `FAIR_PRINCIPLES`, `BIGDATA_VS`, `ISO_COVERAGE`, `TRACEABILITY_MATRIX`).
- **Guard anti-drift**: `vault_norms.py --check-framework` falla si el manifiesto omite
  cualquier id del registro. La doc ya no puede desincronizarse del código en silencio.
- **Política de no-derogación** declarada: nada se elimina; lo reemplazado se anota
  `superseded_by:` conservando su contrato.
- **Changelog consolidado**: entradas faltantes reconstruidas desde git, orden cronológico
  restaurado y hashes `pending` fijados.
- **AP-38 — vocabulario cerrado normalizado al escribir** (`guard+audit`): un censo de
  **17 vaults reales, 2.929 notas**, encontró **54 valores de `status` con solo el 6%
  canónico**, pese a que CN-03 lo audita desde v38. La causa no eran los agentes: el
  toolkit publicaba **nueve** vocabularios de `status` en competencia y auditaba contra
  uno. `normalize_status()` corrige en `vault_write`, `DOMAIN_STATUS_VOCABS` separa el eje
  de dominio (`test_result`, `bug_state`…) del ciclo de vida. Cobertura: 608 de 609 notas.
- **AP-39 — vocabulario abierto con memoria** (`guard+audit`): 1.180 tags para 6.358 usos,
  **45% usados una sola vez** y una tasa de invención **plana durante tres meses**. Los
  tags se resuelven contra el registro antes de escribir y el término nuevo se admite pero
  **queda anotado** en la bitácora append-only `19_Audits/vocabulary/tag-ledger.json` con
  quién, cuándo y en qué nota. Heal: `vault_tags --backfill-ledger`.
- **AP-40 — contrato publicado que la CLI rechaza** (`guard+audit`): **45 de 82 tools**
  publicaban en el catálogo MCP parámetros que su propio `argparse` no acepta, y como el
  servidor compone `--<param>` literal, más de la mitad de la superficie MCP fallaba en cada
  invocación. Había un guard de sincronía en verde: comparaba el JSON contra el Python del
  que se genera, y **dos copias de la misma equivocación coinciden**. Ahora el contrato se
  deriva del script por AST. Audit: `vault_mcp_catalog --check-params`.
- **AP-41 — máquina de estados declarada sin verificar** (`guard+audit`):
  `STATUS_TRANSITIONS` existía desde v38 y su único consumidor era su propio test, así que
  una nota `archived` podía volver a `draft`. El camino de lectura que hacía falta para
  comprobarlo estaba **en la rama del `else`**, la del caso en que la nota no existe: cada
  actualización acuñaba un `id` nuevo, reseteaba `createdAt` y degradaba el estado a
  `draft`. Guard en `vault_write`, audit sobre `.history/`, sin heal — el estado actual es
  un hecho y el camino irregular es la información.
- **AP-42 — tool publicada sin haberse ejecutado nunca** (`guard+audit`): `--help` demuestra
  que el `argparse` se construye, nada más. El primer barrido real —el ejemplo documentado
  de cada tool, contra una copia desechable del sandbox— dio **41 de 87 fallando**, y 36 lo
  hacían porque el `example` del catálogo usaba flags que la propia CLI rechaza: AP-40
  trasladado a la documentación, con el usuario copiando del README algo que no corre.
  Corregidas las 41, la baseline nació en **0**: guard duro desde el primer día.
  Gate: `vault_smoke --check --strict`.
- **AP-43 — norma sin refuerzo en el punto de uso** (`guard+audit`): el catálogo de normas
  estaba completo y era invisible — el agente se enteraba de que una norma existe al
  incumplirla, y solo si era una de las 14 que previenen en vez de una de las 33 que solo
  detectan. Ahora **el vault le habla al agente en cada interacción**: `wrap_main` añade a
  cada resultado un bloque `vault_says` con la norma que acaba de actuar, cuántas notas
  cambiaron y qué mirar después, rotando el foco para que el refuerzo no se vuelva ruido.
  Vive en el único punto por el que ya pasa la salida de todas las tools, porque una capa
  que hubiera que invocar tool por tool sería el registro-que-nadie-consume de siempre.
  Consulta: `vault_voice --tool <tool>` / `--coverage`.
- **Grupo 36 y tres secciones nuevas**, derivadas de medir y no de diseñar: `18_Bugs/`
  (`vault_bug_save` — el defecto tiene ciclo propio: síntoma → causa raíz → corrección
  verificada), `19_Audits/` (la bitácora del vault) y `20_Quarantine/` (`vault_quarantine`
  — retener sin borrar, porque la alternativa a retener no es limpiar, es `rm`).

---

## Novedades v38.1 — Contención, idempotencia y enforcement total

- **AP-36** (critical): toda operación escribe solo dentro del vault, es idempotente
  y deja artefactos rastreables. Backups en `VAULT_ROOT/vault-backups/`, `.bak` de
  moves en `00_System/.trash/`, stubs de mantenimiento en `02_Observability/maintenance/stubs/`.
- **0 normas con enforcement `manual`**: las 73 normas del catálogo tienen guard o audit.
  `python scripts/vault_norms.py --audit [--root X]` audita AP-06/07/09/10/15/19/36, CN-02/03, SP-01.
- **Saneamiento de índices**: tablas con `| [[stem]] | Título | ... |` (nunca alias en
  celda); `python scripts/vault_section_index.py --heal` cura índices legacy; escribir
  un `index.md` a mano dispara la regeneración canónica automática.
- **`STATUS_VOCAB` unificado** (12 valores) como fuente única del vocabulario de `status`.
- **Vault-root lazy**: `set_vault_root()/get_vault_root()` — traces/locks/índices siguen
  al `--root` objetivo.

---

## Quick Start

### 1. Clonar e instalar

```bash
git clone https://github.com/devcicm/Vault-Obsidian-Architecture.git
```

Los scripts no tienen dependencias externas. Solo Python 3.9+.

### 2. Inicializar un vault nuevo

La estructura correcta para un consumer repo es:

```
mi-repo/
├── scripts/          ← copiar aquí (gitignoreados)
├── vault-mi-proyecto/ ← vault vive aquí
└── ...resto del proyecto
```

`vault_io.py` detecta automáticamente el directorio `vault-*/` al ejecutarse. No requiere configuración de path.

```bash
# Crear el directorio del vault dentro del repo
mkdir vault-mi-proyecto

# Copiar scripts al repo (fuera del vault, gitignoreados)
cp -r Vault-Obsidian-Architecture/scripts ./scripts

# v34: un solo comando hace todo el bootstrap (carpetas + version + indexes + audit)
# Crea las 22 carpetas estándar, aplica migraciones hasta v39, auto-indexa, agrega
# scaffold primers en secciones vacías, y reporta el health score inicial.
python scripts/vault_init.py

# Equivalente manual (legacy, v30) — si necesitas paso a paso:
# python scripts/vault_standard_upgrade.py --init v32
# python scripts/vault_standard_upgrade.py --to v32
# for folder in 00_System 01_Projects ... 16_AI_Governance 99_Index; do
#   python scripts/vault_section_index.py --folder "$folder"
# done

# Health check baseline (debe dar 100/100 con vault recién inicializado)
python scripts/vault_audit.py
```

### 3. `.gitignore` para el consumer repo

```gitignore
.claude/
vault-*/scripts/
vault-backups/
```

### 4. Documentar el proyecto

```bash
# Identidad del vault
python scripts/vault_write.py --folder "00_System" \
  --title "Vault Identity" \
  --meta '{"cia_integrity":"high","agent":"claude","type":"identity"}' \
  --content "Vault del proyecto X. Agente: claude."

# Overview del proyecto
python scripts/vault_project_overview.py \
  --project "mi-proyecto" \
  --description "Descripción del proyecto" \
  --runtime "Node.js 20"

# Documentar un módulo (IEEE 1016) e inyectar @vault: en el archivo fuente
python scripts/vault_code_module.py \
  --project "mi-proyecto" \
  --file_path "src/services/AuthService.ts" \
  --description "Servicio de autenticación JWT" \
  --language typescript \
  --iso_type service \
  --tag-source

# Auditar trazabilidad bidireccional código ↔ vault
python scripts/vault_code_sync.py --project "mi-proyecto" --report
python scripts/vault_code_sync.py --project "mi-proyecto" --fix   # inyecta @vault: donde falte

# Auditar el vault
python scripts/vault_audit.py
```

---

## CLI consolidada — `cli/`

Las 106 tools bajo un único punto de entrada, con búsqueda, planificación de
concurrencia y guardas de seguridad:

```bash
python -m cli find "backup grafo"        # las tools como fragmentos buscables
python -m cli doctor --pretty            # raíz, contrato, locks de artefactos
python -m cli batch --file lote.json --parallel 4 --verify-integrity
python -m cli scan --races --summary     # condiciones de carrera en los scripts
```

Ejecuta varias tools a la vez por olas sin pisarse (modelo EXCLUSIVE / GUARDED /
GLOBAL, con la concurrencia sobre artefactos compartidos concedida **por
verificación AST**, no por declaración), escanea el contenido por inyección de
directivas antes de escribir, y contrasta lo que cambió en el vault contra lo
que el plan declaraba.

Guía: [`cli/README.md`](cli/README.md) · Referencia de comandos:
[`cli/COMMANDS.md`](cli/COMMANDS.md).

---

## Las 106 tools activas — 37 grupos

| Grupo | Tools |
|---|---|
| 1 — Core | `vault_write`, `vault_read`, `vault_search`, `vault_list`, `vault_append`, `vault_diff`, `vault_merge` |
| 2 — Observabilidad | `vault_log_error` |
| 3 — Patrones | `vault_pattern_save`, `vault_pattern_list` |
| 4 — Diagramas | `vault_diagram_save`, `vault_relation_add` |
| 5 — Conocimiento | `vault_knowledge_save`, `vault_knowledge_get` |
| 6 — Salud del vault | `vault_audit`, `vault_validate`, `vault_graph` |
| 7 — Runbooks | `vault_runbook_save`, `vault_runbook_log` |
| 8 — Infraestructura | `vault_infra_save`, `vault_infra_map`, `vault_env_save` |
| 9 — Migración | `vault_migrate_docs`, `vault_migrate_rollback` |
| 10 — Línea de tiempo | `vault_timeline` |
| 11 — Vista del proyecto | `vault_project_status`, `vault_project_overview` |
| 12 — Código | `vault_code_module`, `vault_code_relation`, `vault_code_map`, `vault_code_query`, `vault_code_sync` |
| 13 — Backups | `vault_backup`, `vault_backup_list`, `vault_restore` |
| 14 — Seguridad | `vault_security_scan` |
| 15 — Índices | `vault_section_index`, `vault_master_index`, `vault_reindex` |
| 16 — Bibliografía | `vault_bibliography_save` |
| 17 — Drift Detection | `vault_drift_detect` |
| 18 — Flujos | `vault_flow_save` |
| 19 — Requerimientos | `vault_requirement_save` |
| 20 — Tests | `vault_test_save` |
| 21 — IA Governance | `vault_ai_decision` |
| 22 — Versionado | `vault_standard_upgrade`, `vault_onboard` |
| 23 — Change Log | `vault_change_log` |
| 24 — Data Quality | `vault_quality_check`, `vault_fundamentals` |
| 25 — Propagación | `vault_impact`, `vault_propagate` |
| 26 — Tokens | `vault_tokens`, `vault_token_counter`, `vault_token_service` |
| 27 — Session Delta y Tags | `vault_delta`, `vault_tags` |
| 28 — Normas y Etiquetas | `vault_norms`, `vault_code_tag` |
| 29 — Producción y SRE | `vault_incident_save`, `vault_slo_save` |
| 30 — Release y Entornos | `vault_env_matrix`, `vault_release_save` |
| 31 — Riesgos y Calidad | `vault_risk_save`, `vault_privacy_save`, `vault_ncr_save` |
| 32 — Bootstrap | `vault_init` |
| 33 — Corrección automática | `vault_fix_brackets` |
| 34 — Memoria de Contexto | `vault_preferences`, `vault_query_parse`, `vault_subgraph`, `vault_context_pack`, `vault_ingest` |

Ver **[scripts/README.md](./scripts/README.md)** para contratos completos con parámetros, ejemplos y protocolo de sesión.

---

## Protocolo de sesión (resumen)

```bash
# Inicio de sesión
python scripts/vault_standard_upgrade.py --check        # verificar versión
python scripts/vault_reindex.py                         # actualizar índice + hash-index
python scripts/vault_audit.py                           # baseline de salud + tagHealth
python scripts/vault_delta.py --snapshot                # guardar baseline de hashes
python scripts/vault_drift_detect.py --path "." --project {slug} --mode snapshot

# Cierre de sesión
python scripts/vault_delta.py                           # qué cambió, qué está stale
python scripts/vault_drift_detect.py --path "." --project {slug} --mode report
python scripts/vault_tags.py                            # actualizar tag registry
python scripts/vault_reindex.py --graph
python scripts/vault_audit.py                           # healthScore ≥ baseline
python scripts/vault_spec_memory.py --check             # actualizar spec-memory
```

---

## CIA schema + Data Quality (v27–v28)

Cada nota generada incluye clasificación de seguridad y calidad:

```yaml
cia_integrity:    high        # critical | high | medium | low
cia_availability: medium      # high | medium | low
cia_sensitivity:  internal    # public | internal | restricted
agent:            claude      # quién generó la nota (F7 AUTENTICIDAD)
```

`vault_quality_check` evalúa 9 dimensiones por nota (integridad, consistencia, completitud, exactitud, validez, actualidad, autenticidad, no-repudio, unicidad) y genera `00_System/quality-index.json`.

### 8 Fundamentos de Datos (F1–F8)

Cada tool está mapeada a uno o más fundamentos. `vault_fundamentals` es el registro canónico.

| ID | Principio | Tools clave |
|---|---|---|
| F1 | INTEGRIDAD | `vault_write`, `vault_validate`, `vault_quality_check` |
| F2 | CONSISTENCIA | `vault_audit`, `vault_graph`, `vault_impact`, `vault_propagate` |
| F3 | COMPLETITUD | `vault_write`, `vault_append`, `vault_knowledge_save` |
| F4 | EXACTITUD | `vault_drift_detect`, `vault_diff` |
| F5 | VALIDEZ | `vault_validate`, `vault_security_scan` |
| F6 | ACTUALIDAD | `vault_audit`, `vault_drift_detect`, `vault_backup` |
| F7 | AUTENTICIDAD | `vault_write`, `vault_ai_decision`, `vault_bibliography_save` |
| F8 | NO_REPUDIO | `vault_change_log`, `vault_log_error`, `vault_timeline` |

---

## Seguridad (v28)

Todas las tools de escritura incluyen tres capas de protección:

| Capa | Mecanismo | Qué previene |
|---|---|---|
| Path validation | `assert_within_vault()` en `vault_io.py` | Path traversal absoluto (`/etc/passwd`) y relativo (`../../`) |
| Atomic writes | `atomic_write_text` / `atomic_write_json` | Escrituras parciales por kill del proceso |
| CIA frontmatter | Campos obligatorios en los 12 scripts de escritura | Notas sin clasificación de seguridad |

---

## Implementaciones de referencia

### vault-electron-fingerprint

Sistema de control de asistencia con autenticación biométrica.

- **Stack:** ElectronJS 31 + TypeScript + better-sqlite3 + motor .NET C# (sensor DP4500)
- **Vault:** 13 notas — arquitectura, ERD, 2 flujos biométricos, BiometricService (IEEE 1016), API engine, schema SQLite, infra map, envs
- **Health score al cierre:** 100/100 · 0 huérfanas · 0 links rotos · 21 entradas en search index
- **Repo:** [ElectronJS---Autenticacion-por-huella-dactilar](https://github.com/devcicm/ElectronJS---Autenticacion-por-huella-dactilar) · rama `sistema-asistencia` · carpeta `vault-electron-fingerprint/`

---

## La especificación completa

**[vault-obsidian-architecture.md](./vault-obsidian-architecture.md)** — v34, 5500+ líneas.

Contiene:
- 8 principios de diseño
- 106 tools con contratos exactos (parámetros, retorno, error codes, cuándo usar)
- 49 normas: 61 antipatrones (AP-01–AP-37), 6 patrones (PAT-1–PAT-6), 3 SP, 3 CN
- norm_refs auto-embebido en frontmatter + vault_code_tag para etiquetas en código fuente
- 8 Fundamentos de Datos (F1–F8) con trazabilidad a tools
- CIA schema completo con semántica por tipo de nota
- Data Quality framework (9 dimensiones, índice persistente)
- Propagación graph-aware (BFS sobre wiki-links, 3 estrategias)
- **Spec-driven design:** tool-spec.json + vault_spec_validate — contratos formales antes de implementar
- **Trazabilidad bidireccional:** @vault: tag en código fuente + vault_code_sync para auditar gaps código↔vault
- **Grupo 32 — Bootstrap:** `vault_init` para inicializar un vault fresco en 1 comando (17 folders + scaffolds + audit)
- **Grupo 34 — Memoria de Contexto:** eje consulta → contexto. `vault_query_parse`
  (lenguaje natural → consulta estructurada), `vault_subgraph` (K semillas, N saltos),
  `vault_context_pack` (rerank + Top-K bajo presupuesto de tokens), `vault_preferences`
  (contexto estable del usuario) y `vault_ingest` (ingesta con pre-vuelo anti-poison)
- **nextActions prescriptivo:** `vault_audit` ahora devuelve qué hacer para mantener 100/100
- Grupos 29-31: Producción/SRE, Release/Entornos, Riesgos/Calidad (ISO 20000, 22301, 12207, 31000, 27701, 9001)
- Mapa canónico script→carpeta (tabla authoritative)
- Protocolo de inicialización corregido con comandos exactos
- Protocolo de sesión para LLMs remotos (Claude API, GPT, Gemini, DeepSeek)
- Sistema de versionado con migraciones automáticas (v19 → v34)
- Changelog completo (v1 → v34)
- Compatibilidad con Obsidian Desktop

---

## Scripts — estructura del repositorio

```
scripts/                    ← 136 archivos Python (106 tools del catálogo + 8 archivadas en _archived/ + internas/meta)
├── vault_io.py             — I/O base: _detect_vault_root, assert_within_vault, atomic_write_text/json, file_lock
├── vault_errors.py         — wrap_main (timeout 60s), emit_ok, trace log
├── vault_write.py          — tool principal de escritura (guards AP-20, AP-21, norm_refs auto-embed)
├── vault_audit.py          — health score (CIA-weighted), DQ health, propagation pending, norm_code, nextActions
├── vault_standard_upgrade.py — migraciones v19→v34, --init, --check, --validate
├── vault_init.py           — bootstrap de 1 comando (17 folders + scaffolds + master_index + reindex + audit)
├── vault_code_module.py    — documentación IEEE 1016 para módulos de código (--tag-source inyecta @vault:)
├── vault_code_sync.py      — auditoría bidireccional código↔vault (complete/missing_tag/orphan, --fix)
├── vault_flow_save.py      — flujos con Mermaid embebido
├── vault_infra_save.py     — componentes de infraestructura + mapa de red auto-generado
├── vault_knowledge_save.py — conocimiento estructurado por categoría
├── vault_diagram_save.py   — diagramas Mermaid/ASCII/PlantUML
├── ...                     — 75 scripts adicionales
└── README.md               — referencia completa de parámetros y ejemplos
```

**Requisitos:** Python 3.9+ · sin dependencias externas obligatorias  
**Timeout automático:** todas las tools ≤ 60s (configurable via `VAULT_TOOL_TIMEOUT`)  
**JSON siempre:** cualquier error devuelve `{"ok": false, "error_code": "...", "recovery": {...}}`

---

## Compatibilidad

| Entorno | Soporte |
|---|---|
| Bash / Linux / macOS | Completo |
| PowerShell 5.1 (Windows) | Completo — args JSON con `<>` requieren Bash o archivo temporal |
| Claude Code (CLI) | Nativo — tools invocables como subprocess |
| Claude API / GPT / Gemini | Mediante harness que expone las tools como function calls |
| Obsidian Desktop | Compatible — Mermaid rendering, wiki-links nativos, Graph view |

---

## Licencia

MIT — ver [LICENSE](./LICENSE)
