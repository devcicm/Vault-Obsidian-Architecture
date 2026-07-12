# Vault Obsidian Architecture

**Estándar de diseño para dotar a agentes LLM de memoria documental persistente.**

[![Version](https://img.shields.io/badge/version-v38-blue)](./vault-obsidian-architecture.md)
[![Tools](https://img.shields.io/badge/tools-68_active-green)](./scripts/)
[![Scripts](https://img.shields.io/badge/scripts-93_total-lightblue)](./scripts/)
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
├── 02_Observability/    — errores, vulnerabilidades, métricas, SLOs
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
└── 99_Index/            — search-index.json, graph.json
```

Formato: **Markdown + YAML frontmatter + wiki-links**. Compatible con git, abre en cualquier editor, renderable en Obsidian Desktop.

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
# Crea las 18 carpetas estándar, aplica migraciones hasta v34, auto-indexa, agrega
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

## Las 69 tools activas — 33 grupos

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
- 69 tools con contratos exactos (parámetros, retorno, error codes, cuándo usar)
- 34 normas: 23 antipatrones (AP-01–AP-23), 5 patrones (PAT-1–PAT-5), 3 SP, 3 CN
- norm_refs auto-embebido en frontmatter + vault_code_tag para etiquetas en código fuente
- 8 Fundamentos de Datos (F1–F8) con trazabilidad a tools
- CIA schema completo con semántica por tipo de nota
- Data Quality framework (9 dimensiones, índice persistente)
- Propagación graph-aware (BFS sobre wiki-links, 3 estrategias)
- **Spec-driven design:** tool-spec.json + vault_spec_validate — contratos formales antes de implementar
- **Trazabilidad bidireccional:** @vault: tag en código fuente + vault_code_sync para auditar gaps código↔vault
- **Grupo 32 — Bootstrap:** `vault_init` para inicializar un vault fresco en 1 comando (17 folders + scaffolds + audit)
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
scripts/                    ← 85 archivos Python (69 tools activas + 5 deprecadas + 11 internas/meta)
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
