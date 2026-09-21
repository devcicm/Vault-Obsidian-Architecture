# Visión de producto — Vault Obsidian Architecture

**Versión:** 1.0
**Fecha:** 2026-09-20
**Estado:** Draft

---

## Producto y subproductos

Vault Obsidian Architecture tiene tres niveles de producto:

| Nivel | Alcance | Versión independiente |
|--------|---------|---------------------|
| **Estándar** | Estructura, reglas, contratos, gobernanza. Manifiesto + registros canónicos. | **Sí** — `v40.x` |
| **Toolkit** | Implementación Python/CLI/MCP/gates/migrations. Scripts + paquete `vault/`. | **Sí** — `41.x` (próxima) |
| **Runtime** | Vault concreto de un proyecto: memoria operativa, notas, relaciones, preferencias. | No aplica |

**CLI** y **MCP** son subproductos del toolkit — las dos superficies de entrada
para agentes LLM. Comparten el mismo toolkit, misma gobernanza (a través de
`GobernanzaBase`), mismo catálogo de tools, y mismo runtime.

---

## Problema y premisa

Un proyecto acumula decisiones, errores resueltos, restricciones y conocimiento
operativo. Una conversación aislada no asegura que todo eso llegue a la
siguiente sesión del agente. La persona acaba repitiendo contexto y pierde
visibilidad sobre qué información sustentó el trabajo.

La premisa es que ese conocimiento puede conservarse como documentos con
identidad, metadatos, relaciones y reglas de actualización. El agente puede
recuperarlos después, y una persona puede revisar su contenido y procedencia.

---

## Promesa

| Perspectiva | Promesa |
|-------------|---------|
| **Técnica** | Persistir en Markdown con metadatos, relaciones, trazabilidad y presupuesto de contexto, sin base de datos ni embeddings. |
| **De producto** | Agentes que retoman proyectos con conocimiento auditable por personas. |
| **Simple** | Que tu agente pueda retomar lo aprendido y tú puedas comprobarlo. |

---

## Promesas por subproducto

### CLI (Command Line Interface)

| Perspectiva | Promesa |
|-------------|---------|
| **Técnica** | Ejecuta cualquier tool del toolkit desde shell con pre-vuelo de seguridad (AP-36 containment, anti-poison), planificación de olas y verificación de integridad opcional. |
| **De producto** | Automatización CI/scripts robusta y predecible. |
| **Simple** | `vault run <tool>` funciona sin pensar en paths ni Python. |

**Scope IN:** `run`, `batch`, `plan`, `scan`, `doctor`, `groups`, `find`, `show`; scheduler de olas; safety anti-poison; `--verify-integrity`; timeout configurable.

**Scope OUT:** Interacción MCP; validación semántica de Mermaid/referencias; multi-vault discovery.

### MCP (Model Context Protocol)

| Perspectiva | Promesa |
|-------------|---------|
| **Técnica** | Servidor MCP monolítico, cero dependencias npm, expone 116 tools con guard chain de validación (secret scan, bracket balance, Mermaid syntax, content gate). |
| **De producto** | Agentes LLM en tiempo real con validación semántica profunda. |
| **Simple** | Cualquier IA compatible usa las tools sin configuración. |

**Scope IN:** `tools/call`, `tools/list`; JS-native para 9 tools; validación semántica; multi-vault discovery; resources `vault://`.

**Scope OUT:** Scheduling de olas; verify-integrity; batch execution.

---

## Versionado independiente

```
Estándar: v40.34 (solo contratos documentales)
Toolkit:  41.0 (próxima release con installed operations)
CLI:       v1.0
MCP:       v1.0
```

El toolkit y el estándar NO necesitan coincidir. Un runtime puede leer
documentos de cualquier versión del estándar dentro de la ventana de
compatibilidad.

---

## Flujo de conocimiento

```
evidencia → captura → conocimiento gobernado → persistencia
    → recuperación → selección contextual → siguiente sesión
```

---

## Gobernanza (POO)

La gobernanza se modela como jerarquía de clases:

```
GobernanzaBase (abstract)
  ├── pre_flight(tool, args) → ValidationResult
  ├── post_flight(tool, result, args) → AuditResult
  └── classify_tool(tool) → ToolNature

GobernanzaCLI (override)
  └── _pre_flight_specific: AP-36 containment, anti-poison, required args

GobernanzaMCP (override)
  └── _pre_flight_specific: secret scan, bracket balance,
                            Mermaid syntax, content gate, referenced notes
```

CLI y MCP heredan de `GobernanzaBase` y overridean los métodos específicos
de su superficie. El catálogo y las normas se comparten.

---

## Garantías del sistema

| Base | Alcance |
|------|---------|
| Legibilidad documental | Markdown + YAML frontmatter + wikilinks, sin toolkit |
| Escritura contenida y atómica | Operations que usan el camino común verifican destino y usan temporales |
| Gobernanza verificable | Guards y audits detectan o previenen casos que implementan |
| Trazabilidad y recuperación | Historial, trazas, backups y restauración según cada operación |
| Selección de contexto inspeccionable | Paquete informa qué incluye/excluye y su estimación de tokens |

---

## Qué NO garantiza

- Veracidad, completitud o relevancia por tener alta puntuación de salud
- Recuerdo automático u obediencia del agente
- Cobertura de todos los errores posibles
- Protección de ediciones fuera del toolkit
- Conteo exacto de tokens para cualquier modelo
- Instalación completa en todos los entornos (macOS no está en la CI)

---

## Siguiente lectura

- [PRD-CLI](./prd-cli.md)
- [PRD-MCP](./prd-mcp.md)
- [PRD-Toolkit](./prd-toolkit.md)
- [PRD-Estándar](./prd-estandar.md)
- [Roadmap-CLI](./roadmap/roadmap-cli.md)
- [Roadmap-MCP](./roadmap/roadmap-mcp.md)
