# Vault Obsidian Architecture

**Estándar de diseño para dotar a agentes LLM de memoria documental persistente usando Obsidian como backend.**

[![Version](https://img.shields.io/badge/version-v27-blue)](./vault-obsidian-architecture.md)
[![Tools](https://img.shields.io/badge/tools-53_active-green)](./scripts/)
[![Scripts](https://img.shields.io/badge/scripts-66_total-lightblue)](./scripts/)
[![Python](https://img.shields.io/badge/python-3.9+-yellow)](./scripts/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

---

## ¿Qué es esto?

Un patrón técnico completo para que cualquier agente LLM (Claude, GPT-4, Gemini, modelos locales) mantenga memoria entre sesiones usando una carpeta de archivos Markdown estructurada.

Sin bases de datos. Sin embeddings. Sin infraestructura adicional. Solo archivos Markdown + YAML frontmatter + un conjunto de herramientas bien definidas.

> El agente no necesita Obsidian instalado. Necesita el patrón y las tools.

---

## El problema que resuelve

Los agentes LLM olvidan todo al terminar cada sesión:
- No saben en qué estado quedó el proyecto
- Repiten errores ya resueltos
- No tienen contexto de decisiones técnicas anteriores
- La infraestructura, patrones y reglas de negocio deben re-explicarse cada vez

Este estándar define cómo construir un vault de conocimiento que el agente lee, actualiza y navega como memoria persistente.

---

## El documento

**[vault-obsidian-architecture.md](./vault-obsidian-architecture.md)** — la especificación completa (v27).

Contiene:
- 8 principios de diseño
- Estructura de carpetas con **17 secciones numeradas** (00–16 + 99_Index)
- **53 tools documentadas** con contratos exactos (parámetros, retorno, cuándo usar)
- **26 grupos** de tools organizados por dominio
- **21 antipatrones** (AP-01 a AP-21) con señales de alarma y prevención automática
- **5 patrones recomendados** (PAT-1 a PAT-5)
- **8 Fundamentos de Datos** (F1–F8): INTEGRIDAD, CONSISTENCIA, COMPLETITUD, EXACTITUD, VALIDEZ, ACTUALIDAD, AUTENTICIDAD, NO_REPUDIO
- **CIA schema** en frontmatter: clasificación por integridad, disponibilidad y sensibilidad por nota
- **Data Quality framework**: scoring multidimensional (9 dimensiones) por nota con índice persistente
- **Propagación graph-aware**: análisis de impacto BFS + estrategias de acción sobre el grafo de wiki-links
- **Spec-driven memory**: memoria agéntica unificada con contratos, trazabilidad F1–F8 y loop de validación
- Protocolo de sesión para LLMs remotos (DeepSeek, GPT, Gemini, Claude API)
- Sistema de versionado del estándar con migraciones automáticas (v19 → v27)
- Sistema de change log de gobernanza (quién eliminó qué y por qué)
- Observabilidad de tools: error taxonomy, trace log, timeouts
- Guía de inicialización desde cero
- Compatibilidad con Obsidian Desktop
- Changelog completo (v1 → v27)

---

## Novedades v27 — Data Quality, CIA y Propagación de Cambios

### CIA Schema en frontmatter

Tres campos opcionales nuevos en cualquier nota:

```yaml
cia_integrity:    high        # critical|high|medium|low
cia_availability: high        # high|medium|low
cia_sensitivity:  internal    # public|internal|restricted
dq_validated_at:  "2026-05-11T12:00:00Z"
```

Las notas `cia_integrity: critical/high` tienen umbrales de actualidad más estrictos (15 días vs 30) y penalizan más el health score cuando están stale.

### Data Quality framework

`vault_quality_check` evalúa 9 dimensiones por nota y genera `00_System/quality-index.json`:

| Dimensión | Qué mide |
|---|---|
| integrity | Frontmatter estructuralmente completo |
| consistency | Wiki-links resueltos, type coincide con carpeta |
| completeness | ≥3 líneas de contenido, updatedAt presente |
| accuracy | Documentación refleja realidad del código |
| validity | Campos CIA y status en valores permitidos |
| timeliness | Nota actualizada según umbral CIA |
| authenticity | Campo `agent` presente |
| non_repudiation | Referenciada en change-log |
| uniqueness | Sin duplicados AP-17/AP-18 |

### Propagación graph-aware

```bash
# Analizar impacto de un cambio sobre el grafo de backlinks
python scripts/vault_impact.py --changed "01_Projects/api/overview.md"

# Propagar: marcar notas afectadas + encolar para revisión
python scripts/vault_propagate.py --changed "overview.md" --strategy conservative --action notify,queue

# Integrado en change_log (semi-automático)
python scripts/vault_change_log.py --action updated --path "overview.md" --reason "..." --propagate conservative
```

### Spec-driven memory

`vault_spec_memory` genera `00_System/spec-memory.json` — documento unificado que combina:
- Contratos declarativos de los 53 tools (args requeridos, campos de retorno, error codes)
- Trazabilidad F1–F8 → tools
- Estado del sistema (DQ health, propagation queue, change log)
- Loop de validación con detección de spec drift

```bash
python scripts/vault_spec_memory.py --validate --summary
```

---

## Estructura del vault definida

```
vault-{nombre}/
├── 00_System/          — identidad, reglas, contratos, change-log, standard-version, quality-index, spec-memory
├── 01_Projects/        — proyectos: overview, arquitectura, estado, decisiones, envs
├── 02_Observability/   — errores, antipatrones, vulnerabilidades, métricas, alertas, SLOs
├── 03_Decisions/       — ADRs (Architecture Decision Records)
├── 04_Sessions/        — logs de sesión diarios
├── 05_Patterns/        — patrones con ciclo de vida evolutivo
├── 06_Diagrams/        — ERDs y diagramas Mermaid auto-generados
├── 07_Knowledge/       — glosario, APIs, conceptos, reglas de negocio, configs
├── 08_Runbooks/        — procedimientos operacionales
├── 09_Infrastructure/  — servidores, servicios, redes, pipelines CI/CD
├── 10_Migrated/        — documentación externa en tránsito
├── 11_Code/            — documentación de código IEEE 1016 por módulo
├── 12_Bibliography/    — fuentes externas consultadas por el agente
├── 13_Flows/           — flujos de trabajo, pipelines, ciclos de vida
├── 14_Requirements/    — requerimientos ISO 29148
├── 15_Tests/           — casos de test ISO 29119
├── 16_AI_Governance/   — decisiones de agentes IA (ISO 42001)
└── 99_Index/           — search-index.json, graph.json, keywords-index.json
```

---

## Las 53 tools — resumen por grupo

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
| 12 — Código | `vault_code_module`, `vault_code_relation`, `vault_code_map`, `vault_code_query` |
| 13 — Backups | `vault_backup`, `vault_backup_list`, `vault_restore` |
| 14 — Seguridad | `vault_security_scan` |
| 15 — Índices | `vault_section_index`, `vault_master_index`, `vault_reindex` |
| 16 — Bibliografía | `vault_bibliography_save` |
| 17 — Drift Detection | `vault_drift_detect` |
| 18 — Flujos | `vault_flow_save` |
| 19 — Requerimientos | `vault_requirement_save` |
| 20 — Tests | `vault_test_save` |
| 21 — IA Governance | `vault_ai_decision` |
| 22 — Versionado | `vault_standard_upgrade` |
| 23 — Change Log | `vault_change_log` |
| 24 — Data Quality | `vault_quality_check`, `vault_fundamentals` |
| 25 — Propagación | `vault_impact`, `vault_propagate` |
| 26 — Tokens | `vault_tokens`, `vault_token_counter`, `vault_token_service` |

---

## Implementación de referencia

Este repositorio incluye una implementación de referencia en Python (`scripts/`) con **66 scripts** totales:

- **53 tools activas** (agente-facing) en 26 grupos
- **5 tools legacy** deprecadas (vault_migrate, vault_reorganize, vault_tools, vault_create, vault_render)
- **4 tools internas** (vault_io, vault_link_safety, vault_dataset, vault_index)
- **4 tools meta** (vault_test_runner, vault_compact_contracts, vault_manifest, vault_spec_memory)

**Requisitos:** Python 3.9+ · sin dependencias externas obligatorias

**Ciclo de vida finito:** todas las tools tienen timeout automático de 60s (configurable via `VAULT_TOOL_TIMEOUT`). Cualquier fallo devuelve `{"ok": false, "error_code": "...", "recovery": {...}}`.

**Uso básico:**
```bash
# Verificar versión del estándar antes de cada sesión
python scripts/vault_standard_upgrade.py --check

# Guardar una nota (con guards AP-20 y AP-21)
python scripts/vault_write.py --folder "01_Projects/mi-api" --title "Architecture" --content "## Stack\n..."

# Auditar el estado del vault (health score + DQ)
python scripts/vault_audit.py

# Data Quality — scoring completo del vault
python scripts/vault_quality_check.py --min-score 0.7

# Analizar impacto de cambios en el grafo
python scripts/vault_impact.py --changed "01_Projects/api/overview.md"

# Spec-driven memory — contratos + trazabilidad + validación
python scripts/vault_spec_memory.py --validate --summary

# Registrar eliminación antes de borrar (gobernanza)
python scripts/vault_change_log.py --action deleted --path "07_Knowledge/old.md" --reason "Duplicado"
```

Ver **[scripts/README.md](./scripts/README.md)** para la referencia completa con parámetros, ejemplos y protocolo de sesión.

---

## Protocolo de sesión (resumen)

```bash
# Inicio
python scripts/vault_standard_upgrade.py --check   # 0. verificar versión del estándar
python scripts/vault_reindex.py --check            # 1. verificar índice
python scripts/vault_audit.py                      # 2. baseline de salud + DQ score
python scripts/vault_drift_detect.py --path "." --project {slug} --mode snapshot

# Cierre
python scripts/vault_drift_detect.py --path "." --project {slug} --mode report
python scripts/vault_reindex.py --graph
python scripts/vault_audit.py                      # healthScore ≥ baseline
python scripts/vault_spec_memory.py --check        # actualizar spec-memory.json
```

---

## Los 8 Fundamentos de Datos (F1–F8)

Cada tool está mapeada a uno o más fundamentos. `vault_fundamentals` es el registro canónico.

| ID | Principio | Dimensión DQ | Tools clave |
|---|---|---|---|
| F1 | INTEGRIDAD | integrity | vault_write, vault_validate, vault_quality_check |
| F2 | CONSISTENCIA | consistency | vault_audit, vault_graph, vault_impact, vault_propagate |
| F3 | COMPLETITUD | completeness | vault_write, vault_append, vault_knowledge_save |
| F4 | EXACTITUD | accuracy | vault_drift_detect, vault_diff |
| F5 | VALIDEZ | validity | vault_validate, vault_security_scan |
| F6 | ACTUALIDAD | timeliness | vault_audit, vault_drift_detect, vault_backup |
| F7 | AUTENTICIDAD | authenticity | vault_write, vault_ai_decision, vault_bibliography_save |
| F8 | NO_REPUDIO | non_repudiation | vault_change_log, vault_log_error, vault_timeline |

---

## Adopción

El estándar es agnóstico al lenguaje y al agente. Para adoptarlo:

1. Ejecutar `vault_standard_upgrade --check` si ya tienes un vault (detecta brechas)
2. Crear la estructura de 17 carpetas definida en el spec
3. Implementar las 53 tools en el lenguaje del harness (Python, Node.js, Go, etc.)
4. Cargar el spec como system prompt o instrucción del agente
5. El agente opera sobre el vault usando solo las tools — nunca acceso directo a archivos

**Obsidian Desktop:** el vault puede abrirse directamente en Obsidian. Los diagramas Mermaid se renderizan automáticamente.

---

## Licencia

MIT — ver [LICENSE](./LICENSE)
