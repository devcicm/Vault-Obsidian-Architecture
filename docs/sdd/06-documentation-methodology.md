# Documentation Methodology -- Metodología de Documentación

> ES arriba, EN abajo. Reglas duras para frontmatter, guidelines para contenido.

---

## ES

### Principios de documentación científica

**Principio 1: Trazabilidad atómica** -- Toda declaración debe ser verificable.
- Cita: número de línea, path, hash.
- Cada "norma" tiene enforcing tool + detecting tool.

**Principio 2: Reversibilidad** -- Toda modificación debe ser reversible.
- Toda escritura crea history snapshot.
- Toda eliminación usa change_log antes.
- Toda migración tiene rollback documented.

**Principio 3: Consistencia temporal** -- El vault en T₀ + operación = vault en T₁.
- Idempotencia garantiza esto.
- Hash estable permite verificación.

**Principio 4: Granularidad apropiada** -- No más, no menos.
- Una nota = un concepto.
- Una sección = un dominio.
- Una carpeta = un lifecycle.

**Principio 5: Conectividad explícita** -- Las relaciones son first-class.
- Wiki-links como tejido conectivo.
- `relacionado_con:` en frontmatter cuando aplica.
- Cross-references en lugar de duplicación.

**Principio 6: Evolución documentada** -- Cada cambio tiene historia.
- Changelog por nota (no solo por spec).
- Migration log por upgrade.

### Schema canónico por tipo (regla dura)

| Tipo | Frontmatter obligatorio |
|---|---|
| Pattern | id, title, status, lifecycle_state |
| Requirement | id, title, status, priority |
| Test | id, title, status, coverage |
| Runbook | id, title, status, last_run |
| ADR | id, title, status, date |
| Incident | id, title, severity, status |
| Session | id, title, date, duration |
| SLO | id, title, sli_type, status |
| NCR | id, title, severity, status |
| Risk | id, title, level, treatment |

### Clase de documento por sección (Diátaxis)

Fuente: `vault_registry.SECTION_DOCUMENTACION`. Una nota hereda la clase de su
sección; escribir en una sección una nota de otra clase es colocarla mal.

- **tutorial** -- aprender haciendo: un recorrido guiado de principio a fin
- **guia** -- resolver una tarea concreta: pasos para quien ya sabe qué quiere
- **referencia** -- consultar un dato: descripción exacta de lo que hay
- **explicacion** -- entender por qué: contexto, decisiones y alternativas
- **registro** -- lo que ocurrió, anotado cuando ocurrió (fuera de Diátaxis)
- **indice** -- navegación derivada que regenera una tool (fuera de Diátaxis)

| Sección | Nombre | Clase | Por qué |
|---|---|---|---|
| `00_System` | Sistema | referencia | identidad, reglas y configuración que el agente consulta |
| `01_Projects` | Proyectos | explicacion | estado y contexto de cada proyecto: por qué está como está |
| `02_Observability` | Observabilidad | registro | errores, alertas e incidentes según ocurren |
| `03_Decisions` | Decisiones | explicacion | un ADR explica por qué se eligió una opción y no otra |
| `04_Sessions` | Sesiones | registro | diario de sesión: lo que se hizo, en su fecha |
| `05_Patterns` | Patrones | guia | cómo resolver un problema que se repite |
| `06_Diagrams` | Diagramas | explicacion | representación visual para entender una estructura |
| `07_Knowledge` | Conocimiento | explicacion | conocimiento técnico y conceptual |
| `08_Runbooks` | Runbooks | guia | procedimientos operativos paso a paso |
| `09_Infrastructure` | Infraestructura | referencia | inventario de infraestructura, entornos y configuración |
| `10_Migrated` | Migrados | registro | lo importado se conserva como llegó; su cuadrante es el de su origen |
| `11_Code` | Código | referencia | mapa de módulos de código y sus relaciones |
| `12_Bibliography` | Bibliografía | referencia | fuentes externas consultadas |
| `13_Flows` | Flujos | explicacion | flujos, pipelines y ciclos de vida: cómo encaja el proceso |
| `14_Requirements` | Requerimientos | referencia | requerimientos (ISO 29148): lo que el sistema debe cumplir |
| `15_Tests` | Tests | referencia | casos de prueba y resultados (ISO 29119) |
| `16_AI_Governance` | IA Governance | registro | decisiones y auditorías de agentes IA, en su fecha (ISO 42001) |
| `17_Preferences` | Preferencias | referencia | contexto estable que el agente consulta en cada tarea |
| `18_Bugs` | Bugs | registro | se puebla cuando aparece un bug |
| `19_Audits` | Auditorías | registro | se puebla al ejecutar una auditoría |
| `20_Quarantine` | Cuarentena | registro | se puebla cuando algo entra en cuarentena |
| `21_QA` | QA | registro | eventos de calidad: ejecuciones, métricas y reportes |
| `99_Index` | Índices | indice | índices de navegación que regeneran las tools |

Clases de Diátaxis sin ninguna sección: tutorial.

### Estructura mínima (guideline)

- Pattern: ## Contexto, ## Implementación, ## Trade-offs, ## Evolución
- Requirement: ## Descripción, ## Acceptance Criteria, ## Traceability
- Test: ## Setup, ## Steps, ## Expected, ## Results

### Cuándo crear vs enriquecer

- **Crear** cuando: concepto NO existe, <70% overlap con existente
- **Enriquecer** cuando: overlap topical pero <70%, canónica tiene <3 líneas
- **Archivar** cuando: deprecado por patrón más nuevo, migrado, consolidado

---

## EN

### Scientific documentation principles

(See ES section above.)

### Canonical schema per type (hard rule)

(See table above in ES section.)

### Document class per section (Diátaxis)

(See table above in ES section: `vault_registry.SECTION_DOCUMENTACION`.)

### Minimum structure (guideline)

(See list above in ES section.)

### When to create vs enrich

(See list above in ES section.)
