# Skills — Capacidades del Vault

> Documentación de las **skills** (capacidades reutilizables) que el vault ofrece.
> Esta es documentación de referencia del repo spec, no una nota de vault.
> Bilingual documentation. ES arriba, EN abajo.

---

## ES

### ¿Qué es una skill?

Una **skill** es una capacidad documentada del vault que un agente (humano o
LLM) puede invocar. Cada skill tiene:

- **Propósito** claro (qué resuelve)
- **Invocación** (cómo se llama)
- **Outputs** (qué genera)
- **Restricciones** (cuándo NO usarla)
- **Prerrequisitos** (qué necesita del vault)
- **Tests** (cómo verificar que funciona)

### Skills disponibles

| Skill | Versión | Ubicación | Descripción |
|---|---|---|---|
| `vault-sdd-init` | v1.0 | `scripts/vault_sdd_init.py` | Inicializa el SDD (Spec-Driven Development documentation) de un vault |

### `vault-sdd-init` v1.0

```
+---------------------------------------------+
|  VAULT SDD · Spec-Driven Development        |
|     Idempotent · Traceable · Observable     |
+---------------------------------------------+
```

#### Propósito

Auto-genera la documentación SDD completa de un vault en `docs/sdd/`.
14 archivos bilingües (ES + EN paralelo) que cubren principios, state machines,
antipatrones, metodología de documentación, métricas y roadmap.

#### Invocación

```bash
# Modo normal: genera los 14 archivos en docs/sdd/
python scripts/vault_sdd_init.py --bilingual

# Dry-run: muestra plan sin escribir
python scripts/vault_sdd_init.py --bilingual --dry-run

# Especificar vault root alternativo
python scripts/vault_sdd_init.py --vault-root /path/to/vault --bilingual

# Forzar re-generación
python scripts/vault_sdd_init.py --bilingual --force
```

#### Comportamiento

1. **Scan vault** — Lee `tool-spec.json`, `NORM_CATALOG`, configuración de secciones.
2. **Detect drift** — Verifica versión actual, normas faltantes, métricas.
3. **Generate parts** — Para cada documento del SDD, aplica template con contenido detectado.
4. **Write to docs/sdd/** — 14 archivos + integrity report + gaps.
5. **Run integrity checker** — Valida coherencia entre docs generados.

#### Outputs (14 archivos en `docs/sdd/`)

| Archivo | Descripción |
|---|---|
| `README.md` | Índice bilingüe |
| `00-principles.md` | Principios fundamentales |
| `01-state-machines.md` | Lifecycle states por dominio |
| `02-implementation.md` | Guía para autores de tools |
| `03-usage.md` | Guía para consumers |
| `04-antipatterns.md` | Catálogo AP-01..AP-25 |
| `05-reference-matrix.md` | Pattern → Detect → Fix |
| `06-documentation-methodology.md` | La ciencia de qué documentar |
| `07-process-antipatterns.md` | Antipatrones de proceso |
| `08-roadmap.md` | Hallazgos pendientes priorizados |
| `09-metrics.md` | Métricas de salud |
| `10-appendices.md` | ISO standards, glosario |
| `integrity-report.json` | Output del checker |
| `gaps.md` | Manual fill |

#### Restricciones

- **READ-ONLY** sobre el resto del vault. La skill SOLO escribe en `docs/sdd/`.
- **NO modifica notas existentes**.
- **NO crea notas nuevas** fuera de `docs/sdd/`.
- **Idempotente**: correr 2× produce mismo output.
- **No pisa documentación manual**: respeta contenido manual en `gaps.md`.

#### Prerrequisitos

- vault-spec >= v36.0 (con AP-24, AP-25 registrados)
- `NORM_CATALOG` completo (25 antipatrones)
- `atomic_write_text` con fix de temp leak (FASE 0.4)
- CI workflow activo
- Secret scanning operativo

#### Tests

- `tests/test_vault_sdd_init.py` — 15 tests cubriendo generadores, drift, idempotency.

#### Logo

```
+---------------------------------------------+
|  VAULT SDD · Spec-Driven Development        |
|     Idempotent · Traceable · Observable     |
+---------------------------------------------+
```

---

## EN

### What is a skill?

A **skill** is a documented capability of the vault that an agent (human or
LLM) can invoke. Each skill has:

- **Purpose** (what it solves)
- **Invocation** (how to call it)
- **Outputs** (what it generates)
- **Constraints** (when NOT to use it)
- **Prerequisites** (what it needs from the vault)
- **Tests** (how to verify it works)

### Available skills

(See table above in ES section.)

### `vault-sdd-init` v1.0

#### Purpose

Auto-generates the complete SDD (Spec-Driven Development) documentation of
a vault in `docs/sdd/`. 14 bilingual documents (ES + EN in parallel) covering
principles, state machines, antipatterns, documentation methodology, metrics
and roadmap.

#### Invocation

(See ES section above.)

#### Behavior

(See ES section above.)

#### Outputs

(See table above in ES section.)

#### Constraints

(See ES section above.)

#### Prerequisites

(See ES section above.)

#### Tests

(See ES section above.)

#### Logo

(See ASCII art above in ES section.)