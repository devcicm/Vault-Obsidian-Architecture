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

### Minimum structure (guideline)

(See list above in ES section.)

### When to create vs enrich

(See list above in ES section.)
