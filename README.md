# Vault Obsidian Architecture

**Estándar de diseño para dotar a agentes LLM de memoria documental persistente usando Obsidian como backend.**

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

**[vault-obsidian-architecture.md](./vault-obsidian-architecture.md)** — la especificación completa.

Contiene:
- 8 principios de diseño
- Estructura de carpetas con 13 secciones numeradas
- **37 tools documentadas** con contratos exactos (parámetros, retorno, cuándo usar)
- Protocolo de migración segura en 5 fases con gates de validación
- 15+ anti-patrones con señales de alarma y prevención
- 12 casos de uso concretos con flujos paso a paso
- Protocolo de sesión para LLMs remotos (DeepSeek, GPT, Gemini, Claude API)
- Guía de inicialización desde cero
- Compatibilidad con Obsidian Desktop
- Changelog completo (v1 → v20)

---

## Estructura del vault definida

```
vault-{nombre}/
├── 00_System/          — identidad, reglas, contratos del agente
├── 01_Projects/        — proyectos: overview, arquitectura, estado, decisiones, envs
├── 02_Observability/   — errores, antipatrones, vulnerabilidades, métricas, alertas, SLOs
├── 03_Decisions/       — ADRs (Architecture Decision Records)
├── 04_Sessions/        — logs de sesión diarios
├── 05_Patterns/        — patrones con ciclo de vida evolutivo
├── 06_Diagrams/        — ERDs y diagramas Mermaid auto-generados
├── 07_Knowledge/       — glosario, APIs, conceptos, reglas de negocio, configs
├── 08_Runbooks/        — procedimientos operacionales
├── 09_Infrastructure/  — servidores, servicios, redes, pipelines CI/CD
├── 10_Migrated/        — documentación externa migrada
├── 11_Code/            — documentación de código por módulo
└── 99_Index/           — search-index.json y graph.json
```

---

## Las 37 tools — resumen por grupo

| Grupo | Tools |
|---|---|
| 1 — Escritura y lectura | `vault_write`, `vault_read`, `vault_append`, `vault_list` |
| 2 — Proyecto | `vault_project_status`, `vault_env_save`, `vault_diff` |
| 3 — Patrones | `vault_pattern_save`, `vault_pattern_list` |
| 4 — Decisiones y errores | `vault_decision_save`, `vault_log_error` |
| 5 — Conocimiento | `vault_knowledge_save`, `vault_knowledge_get` |
| 6 — Búsqueda y grafo | `vault_search`, `vault_graph` |
| 7 — Runbooks | `vault_runbook_save`, `vault_runbook_log` |
| 8 — Infraestructura | `vault_infra_save`, `vault_infra_map` |
| 9 — Migración | `vault_migrate_docs`, `vault_migrate_rollback`, `vault_merge` |
| 10 — Línea de tiempo | `vault_timeline` |
| 11 — Vista consolidada | `vault_project_overview` |
| 12 — Código | `vault_code_module`, `vault_code_relation`, `vault_code_map` |
| 13 — Backups | `vault_backup`, `vault_backup_list`, `vault_restore` |
| 14 — Seguridad | `vault_security_scan` |
| 15 — Índices de navegación | `vault_section_index`, `vault_master_index`, `vault_reindex` |

---

## Implementación de referencia

Este repositorio incluye una implementación de referencia en Python (`scripts/`) con los 44 scripts que implementan las 37 tools del estándar.

**Requisitos:** Python 3.9+ · PyYAML (`pip install pyyaml`)

**Uso básico:**
```bash
# Guardar una nota
python scripts/vault_write.py --folder "01_Projects/mi-api" --title "Architecture" --content "## Stack\n..."

# Buscar en el vault
python scripts/vault_search.py --query "autenticación JWT"

# Auditar el estado del vault
python scripts/vault_audit.py

# Backup antes de una migración
python scripts/vault_backup.py --label "pre-migration"
```

---

## Adopción

El estándar es agnóstico al lenguaje y al agente. Para adoptarlo:

1. Crear la estructura de carpetas definida en el spec
2. Implementar las 37 tools en el lenguaje del harness (Python, Node.js, Go, etc.)
3. Cargar el spec como system prompt o instrucción del agente
4. El agente opera sobre el vault usando solo las tools — nunca acceso directo a archivos

**Obsidian Desktop:** el vault puede abrirse directamente en Obsidian. Los diagramas Mermaid se renderizan automáticamente.

---

## Licencia

MIT — ver [LICENSE](../LICENSE)
