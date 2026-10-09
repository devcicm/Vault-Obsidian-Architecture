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
- Los campos de traza de cada clase (ver "Trazabilidad, versionado…"); `relacionado_con:`
  figuraba aquí y ninguna tool lo escribe.
- Cross-references en lugar de duplicación.

**Principio 6: Evolución documentada** -- Cada cambio tiene historia.
- Changelog por nota (no solo por spec).
- Migration log por upgrade.

### Schema canónico por tipo (regla dura)

Fuente: `vault_registry.SCHEMA_POR_TIPO`. La columna de lo obligatorio conserva
lo que esta tabla exigía cuando se escribía a mano; la última dice qué de eso no
escribe el escritor del tipo, medido sobre la nota que deja. Un campo prometido
sin escritor no se exige a nadie: queda publicado hasta que una tool lo escriba
o se anote su `superseded_by`.

| Tipo | Frontmatter obligatorio | Escritor | Prometido sin escritor |
|---|---|---|---|
| Pattern | id, title, status, lifecycle_state | vault_pattern_save | `lifecycle_state` |
| Requirement | id, title, status, priority | vault_requirement_save | ninguno |
| Test | id, title, status, coverage | vault_test_save | `coverage` |
| Runbook | id, title, status, last_run | vault_runbook_save | `last_run` |
| ADR | id, title, status, date | vault_write | `date` |
| Incident | id, title, severity, status | vault_incident_save | ninguno |
| Session | id, title, date, duration | vault_write | `date`, `duration` |
| SLO | id, title, sli_type, status | vault_slo_save | `sli_type`, `status` |
| NCR | id, title, severity, status | vault_ncr_save | ninguno |
| Risk | id, title, level, treatment | vault_risk_save | ninguno |

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

### Trazabilidad, versionado y su correlación con estado y versión

Fuente: `vault_registry.EJES_DOCUMENTACION` y `MODOS_DE_VERSION`. Cada clase de
documento declara con qué se traza --los campos son los que escriben las tools
nombradas-- y cómo se versiona. El estado de la nota puede endurecer ese modo, y
la versión del estándar fija qué contrato de frontmatter se le exige.

#### Eje de trazabilidad y eje de versionado, por clase

| Clase | Se traza con | Campos | Tools | Versionado mientras está abierta |
|---|---|---|---|---|
| tutorial | la referencia que enseña a usar, por wikilink | wikilink en el cuerpo | vault_write | historia |
| guia | los patrones relacionados, los ficheros que toca y el disparador del runbook | `relatedPatterns`, `files`, `trigger` | vault_pattern_save, vault_runbook_save | historia |
| referencia | el requisito por su identificador y el test que lo verifica; el código relacionado va en el cuerpo y en el índice, no en el frontmatter | `req_id`, `related_requirement` | vault_requirement_save, vault_test_save | historia |
| explicacion | las notas relacionadas y la que la sustituye cuando la decisión cambia | `related`, `superseded_by` | vault_ingest, vault_supersede | historia |
| registro | su fecha y el test que verifica la corrección | `createdAt`, `verified_by` | vault_bug_save | anexado |
| indice | las notas de las que se deriva, al regenerarse | wikilink en el cuerpo | vault_section_index | regenerado |

#### Modos de versionado

| Modo | Qué significa | Tools | Enforcement |
|---|---|---|---|
| historia | se reescribe en su sitio y la versión anterior queda en .history/ | vault_write, vault_history_compact | guard |
| anexado | solo se añade al final; lo ya escrito no se reescribe | vault_append | recommended |
| sustitucion | la versión nueva es otra nota y la anterior declara superseded_by | vault_supersede | recommended |
| regenerado | artefacto derivado: se regenera desde las notas y no se versiona | vault_section_index | guard |
| inmutable | estado terminal: ni se reescribe ni se sustituye, queda como hecho | vault_write | recommended |

#### Correlación estado → versionado

El régimen de cada `status` se deriva de `STATUS_TRANSITIONS`:

- **abierto** -- puede volver a draft: se edita con el modo de su clase
- **cerrado** -- ya no vuelve a draft: un cambio de contenido es una nota nueva
- **terminal** -- sin transiciones de salida: queda como hecho

| status | Régimen | tutorial | guia | referencia | explicacion | registro | indice |
|---|---|---|---|---|---|---|---|
| `planned` | abierto | historia | historia | historia | historia | anexado | regenerado |
| `draft` | abierto | historia | historia | historia | historia | anexado | regenerado |
| `in-progress` | abierto | historia | historia | historia | historia | anexado | regenerado |
| `reviewed` | abierto | historia | historia | historia | historia | anexado | regenerado |
| `approved` | cerrado | sustitucion | sustitucion | sustitucion | sustitucion | anexado | regenerado |
| `implemented` | cerrado | sustitucion | sustitucion | sustitucion | sustitucion | anexado | regenerado |
| `verified` | cerrado | sustitucion | sustitucion | sustitucion | sustitucion | anexado | regenerado |
| `deprecated` | cerrado | sustitucion | sustitucion | sustitucion | sustitucion | anexado | regenerado |
| `obsolete` | cerrado | sustitucion | sustitucion | sustitucion | sustitucion | anexado | regenerado |
| `archived` | terminal | inmutable | inmutable | inmutable | inmutable | anexado | regenerado |
| `stub` | abierto | historia | historia | historia | historia | anexado | regenerado |
| `template` | cerrado | sustitucion | sustitucion | sustitucion | sustitucion | anexado | regenerado |

#### Correlación versión del estándar → contrato de nota

El vault declara la versión que aplica en `00_System/standard-version.json` (`vault_standard_upgrade`), que lo mide contra el contrato de esa versión. `vault_validate --check cumplimiento` publica qué versiones cumple cada nota, y `vault_validate --contrato vNN` aplica el de una versión concreta. Solo se listan las versiones en que el contrato cambió; fuente: `vault_contrato_nota.HISTORIA`.

| Versión | Autoridad | Requeridos en notas de contenido | Qué cambió | Fuente |
|---|---|---|---|---|
| v18 | manifiesto | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` | AP-12 en el manifiesto: los seis campos obligatorios en toda nota; ninguna tool lo aplica | `manifiesto` |
| v21 | manifiesto | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` | el escritor pone agent en las notas nuevas | `MIGRATIONS` |
| v25 | validador | `id`, `title` | primer validador: exige id y title, menos que AP-12, que el manifiesto de v25 sigue escribiendo igual | `git` |
| v27 | validador | `id`, `title` | si están, el valor CIA pertenece al vocabulario y agent no está vacío | `MIGRATIONS` |
| v28 | validador | `id`, `title` | los scripts de escritura ponen CIA y agent | `MIGRATIONS` |
| v30 | validador | `id`, `title` | vocabulario de status auditado (CN-03) | `MIGRATIONS` |
| v37 | validador | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags` | requeridos; CIA, agent y tags solo en notas de contenido, y los índices quedan fuera del contrato. type y status, recomendados | `git` |
| v37 | validador | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags` | el escritor los pone por defecto y vault_audit penaliza su ausencia | `git` |
| v41 | validador | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags`, `type`, `status` | requeridos en notas de contenido, por presencia: el valor lo sigue juzgando vault_audit | `MIGRATIONS` |
| v41 | validador | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags`, `type`, `status` | clase sin_seccion: un .md fuera de toda sección lleva identidad y timestamps; CIA, agent, tags, type y status son de las notas de sección | `MIGRATIONS` |
| v41 | validador | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags`, `type`, `status` | opcional: la versión del proyecto desde la que rige una nota de arquitectura; el fin sale de superseded_by o del status | `MIGRATIONS` |
| v41 | validador | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags`, `type`, `status` | opcionales: quién responde del contenido y cuándo se comprobó por última vez; si están, responsable no vacío y revisado_en con fecha ISO | `MIGRATIONS` |

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

### Traceability, versioning and their correlation with status and version

(See tables above in ES section: `vault_registry.EJES_DOCUMENTACION`,
`MODOS_DE_VERSION`, `vault_registry.regimen_de_estado` and
`vault_contrato_nota.HISTORIA`.)

### Minimum structure (guideline)

(See list above in ES section.)

### When to create vs enrich

(See list above in ES section.)
