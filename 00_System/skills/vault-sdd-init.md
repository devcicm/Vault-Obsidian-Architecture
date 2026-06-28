---
title: "vault-sdd-init (skill)"
id: skill-vault-sdd-init
type: skill
status: active
introduced_version: v36.0
tags: ["skill", "documentation", "framework", "sdd", "spec-driven"]
cia_integrity: high
cia_availability: medium
cia_sensitivity: internal
agent: vault_init
norm_refs: ["AP-24", "AP-25"]
---

# vault-sdd-init — Spec-Driven Development Initializer

```
╔════════════════════════════════════════════════════════════════════════════╗
║  ██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗    ███████╗██████╗ ██████╗       ║
║  ██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝    ██╔════╝██╔══██╗██╔══██╗      ║
║  ██║   ██║███████║██║   ██║██║     ██║       ███████╗██║  ██║██║  ██║      ║
║  ╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║       ╚════██║██║  ██║██║  ██║      ║
║   ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║       ███████║██████╔╝██████╔╝      ║
║    ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝       ╚══════╝╚═════╝ ╚═════╝       ║
║                                                                            ║
║              Spec-Driven Development · Spec-Driven Development             ║
╚════════════════════════════════════════════════════════════════════════════╝
```

> **Skill:** Capacidad del vault para auto-generar su propio SDD
> (Spec-Driven Development documentation). Esta nota es el **manifiesto** de
> la skill: define QUÉ hace, CÓMO se usa, y DÓNDE encontrar los templates.

## Propósito / Purpose

### ES

Esta skill permite generar automáticamente la documentación SDD completa de
un vault. A partir del análisis del vault (herramientas declaradas en
`tool-spec.json`, normas en `NORM_CATALOG`, state machines detectadas en
`vault_*_save.py`, configuración de secciones, etc.), produce 14 documentos
bilingües (ES + EN paralelo) en `docs/sdd/` que cubren principios, state
machines, antipatrones, metodología de documentación, métricas y roadmap.

El SDD generado documenta el estado del vault **post-fix**. Es decir, primero
se aplican los fixes críticos (FASE 0), luego la skill se ejecuta y produce
el SDD del estado actual limpio.

### EN

This skill auto-generates the complete SDD (Spec-Driven Development)
documentation of a vault. By analyzing the vault (tools declared in
`tool-spec.json`, norms in `NORM_CATALOG`, state machines detected in
`vault_*_save.py`, section configuration, etc.), it produces 14 bilingual
documents (ES + EN in parallel) in `docs/sdd/` covering principles, state
machines, antipatterns, documentation methodology, metrics and roadmap.

The generated SDD documents the vault's **post-fix** state. First, critical
fixes are applied (PHASE 0); then the skill runs and produces the SDD of
the current clean state.

## Invocación / Invocation

```bash
# Modo normal: genera los 14 archivos en docs/sdd/
python scripts/vault_sdd_init.py --bilingual

# Dry-run: muestra plan sin escribir
python scripts/vault_sdd_init.py --bilingual --dry-run

# Especificar vault root alternativo
python scripts/vault_sdd_init.py --vault-root /path/to/vault --bilingual

# Forzar re-generación (bypass idempotency check)
python scripts/vault_sdd_init.py --bilingual --force
```

## Comportamiento / Behavior

### ES

1. **Scan vault** — Lee `tool-spec.json`, `NORM_CATALOG`, configuración de
   secciones, detecta state machines de las tools, cuenta notas, valida
   health score.
2. **Detect drift** — Verifica versión actual, normas faltantes, métricas
   de salud, antipatrones detectados.
3. **Generate parts** — Para cada uno de los 14 documentos del SDD,
   aplica el template correspondiente con el contenido detectado:
   - 00-principles.md — Principios del vault (idempotencia, trazabilidad, etc.)
   - 01-state-machines.md — Lifecycle states de pattern/requirement/test/etc.
   - 02-implementation.md — Guía para autores de tools
   - 03-usage.md — Guía para consumers
   - 04-antipatterns.md — AP-01..AP-25 con fixes
   - 05-reference-matrix.md — Tabla pattern → detect → fix
   - 06-documentation-methodology.md — Ciencia de qué documentar
   - 07-process-antipatterns.md — Antipatrones de proceso
   - 08-roadmap.md — Hallazgos pendientes priorizados
   - 09-metrics.md — healthScore, DQ score, etc.
   - 10-appendices.md — ISO standards, glosario
4. **Inject bilingual** — Cada documento tiene ES + EN en paralelo.
5. **Write to docs/sdd/** — 14 archivos + `integrity-report.json` + `gaps.md`.
6. **Run integrity_checker** — Valida coherencia entre docs generados.
7. **Report gaps** — Lo que falta llenar manualmente.

### EN

1. **Scan vault** — Read `tool-spec.json`, `NORM_CATALOG`, section config,
   detect state machines from tools, count notes, validate health score.
2. **Detect drift** — Check current version, missing norms, health metrics,
   detected antipatterns.
3. **Generate parts** — For each of the 14 SDD documents, apply the
   corresponding template with detected content.
4. **Inject bilingual** — Each document has ES + EN in parallel.
5. **Write to docs/sdd/** — 14 files + `integrity-report.json` + `gaps.md`.
6. **Run integrity_checker** — Validate coherence between generated docs.
7. **Report gaps** — What needs manual fill.

## Outputs / Outputs

```
docs/sdd/
├── README.md                              (índice bilingüe)
├── 00-principles.md                       (~600 líneas, ES + EN)
├── 01-state-machines.md                   (~400 líneas)
├── 02-implementation.md                   (~500 líneas)
├── 03-usage.md                            (~500 líneas)
├── 04-antipatterns.md                     (~700 líneas, AP-01..AP-25)
├── 05-reference-matrix.md                 (~250 líneas)
├── 06-documentation-methodology.md        (~600 líneas)
├── 07-process-antipatterns.md             (~300 líneas)
├── 08-roadmap.md                          (~400 líneas)
├── 09-metrics.md                          (~250 líneas)
├── 10-appendices.md                       (~300 líneas)
├── integrity-report.json                  (output del checker)
└── gaps.md                                (manual fill)
```

Total: ~5000 líneas en 14 archivos.

## Restricciones / Constraints

### ES

- **READ-ONLY** sobre el resto del vault. La skill SOLO escribe en
  `docs/sdd/`.
- **NO modifica notas existentes**.
- **NO crea notas nuevas** fuera de `docs/sdd/`.
- **Idempotente**: correr 2× produce mismo output byte-a-byte (mismo
  timestamp, mismo orden de archivos).
- **No pisa documentación manual**: si `docs/sdd/gaps.md` tiene contenido
  manual, se respeta (la skill solo agrega, no reemplaza).

### EN

- **READ-ONLY** on the rest of the vault. The skill ONLY writes to
  `docs/sdd/`.
- **DOES NOT modify existing notes**.
- **DOES NOT create new notes** outside `docs/sdd/`.
- **Idempotent**: running twice produces same output byte-for-byte
  (same timestamp, same file order).
- **Does not overwrite manual documentation**: if `docs/sdd/gaps.md` has
  manual content, it's preserved (the skill only appends, not replaces).

## Versión de la skill / Skill Version

| Versión | Cambios |
|---------|---------|
| v1.0 (v36.0) | Introducción inicial. 14 documentos generados, bilingüe ES+EN. |

## Prerrequisitos / Prerequisites

### ES

- vault-spec >= v36.0 (con AP-24, AP-25 registrados)
- `NORM_CATALOG` completo (25 antipatrones)
- `atomic_write_text` con fix de temp leak (FASE 0.4)
- CI workflow activo (`.github/workflows/vault-ci.yml`)
- Secret scanning operativo (`vault_secret_scan.py`)

### EN

- vault-spec >= v36.0 (with AP-24, AP-25 registered)
- `NORM_CATALOG` complete (25 antipatterns)
- `atomic_write_text` with temp leak fix (PHASE 0.4)
- CI workflow active (`.github/workflows/vault-ci.yml`)
- Secret scanning operational (`vault_secret_scan.py`)

## Tests / Tests

```
tests/test_vault_sdd_init.py

Cobertura:
- Test que genera los 14 archivos esperados
- Test que contenido es bilingüe (ES + EN en cada doc)
- Test de idempotencia (correr 2× produce mismo output)
- Test que integrity_checker detecta drift de versión
- Test que integrity_checker detecta normas faltantes
- Test que la skill NO modifica archivos fuera de docs/sdd/
- Test que gaps.md lista los hallazgos priorizados
```

## Historial / History

- 2026-06-28 — v1.0: Introducción inicial de la skill (FASE 1A)

## Referencias / References

- `scripts/vault_sdd_init.py` — Thin wrapper
- `scripts/vault_sdd_templates/` — 14 .template.md
- `scripts/vault_sdd_generators/` — 9 generadores
- `scripts/vault_sdd_config/` — 3 yaml
- `scripts/vault_norms.py` — NORM_CATALOG (single source of truth)
- `scripts/tool-spec.json` — Tool contracts (single source of truth)
- `vault-obsidian-architecture.md` — Master spec
- `04_Sessions/2026-06-27-sdd-plan.md` — Plan completo de SDD

## Tags

`["skill", "documentation", "framework", "sdd", "spec-driven"]`