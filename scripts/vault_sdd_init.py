#!/usr/bin/env python3
"""vault_sdd_init — Thin wrapper for the vault-sdd-init skill.

This script is the entry point for the skill declared in
00_System/skills/vault-sdd-init.md. It orchestrates the generation
of the 14 SDD documents by delegating to specialized generators.

Usage:
    python scripts/vault_sdd_init.py --bilingual
    python scripts/vault_sdd_init.py --bilingual --dry-run
    python scripts/vault_sdd_init.py --bilingual --force
    python scripts/vault_sdd_init.py --vault-root /path/to/vault --bilingual
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vault_io import VAULT_ROOT, atomic_write_json, atomic_write_text


SDD_OUTPUT_DIR = "docs/sdd"
SKILL_MANIFEST = "00_System/skills/vault-sdd-init.md"

EXPECTED_OUTPUTS = [
    "README.md",
    "00-principles.md",
    "01-state-machines.md",
    "02-implementation.md",
    "03-usage.md",
    "04-antipatterns.md",
    "05-reference-matrix.md",
    "06-documentation-methodology.md",
    "07-process-antipatterns.md",
    "08-roadmap.md",
    "09-metrics.md",
    "10-appendices.md",
    "integrity-report.json",
    "gaps.md",
]


def utcnow() -> str:
    """Return current UTC timestamp (matches vault_lib.utcnow)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def detect_drift(vault_root: Path) -> dict:
    """Detect drift between vault state and expected invariants."""
    drift = {"version": None, "missing_norms": [], "warnings": []}

    try:
        from vault_standard_upgrade import CURRENT_VERSION

        drift["version"] = CURRENT_VERSION
    except Exception as e:
        drift["warnings"].append(f"Could not read CURRENT_VERSION: {e}")

    try:
        from vault_norms import NORM_CATALOG

        codes = {n["code"] for n in NORM_CATALOG}
        expected = {f"AP-{i:02d}" for i in range(1, 26)}
        expected |= {"PAT-1", "PAT-2", "PAT-3", "PAT-4", "PAT-5"}
        expected |= {"CN-01", "CN-02", "CN-03"}
        expected |= {"SP-01", "SP-02", "SP-03"}
        drift["missing_norms"] = sorted(expected - codes)
    except Exception as e:
        drift["warnings"].append(f"Could not read NORM_CATALOG: {e}")

    return drift


def generate_readme(vault_root: Path, drift: dict) -> str:
    """Generate the README.md index for docs/sdd/."""
    version = drift.get("version", "unknown")
    return f"""# SDD del Vault — Vault SDD

> Documento bilingüe. Versión española arriba, inglesa abajo.
> Bilingual document. Spanish version above, English version below.

---

## ES

### Índice / Index

| # | Documento | Descripción |
|---|---|---|
| 00 | [Principles](./00-principles.md) | Principios fundamentales del vault |
| 01 | [State Machines](./01-state-machines.md) | Lifecycle states por dominio |
| 02 | [Implementation Guide](./02-implementation.md) | Guía para autores de tools |
| 03 | [Usage Guide](./03-usage.md) | Guía para consumers |
| 04 | [Antipatterns](./04-antipatterns.md) | Catálogo AP-01..AP-25 |
| 05 | [Reference Matrix](./05-reference-matrix.md) | Pattern → Detect → Fix → Prevent |
| 06 | [Documentation Methodology](./06-documentation-methodology.md) | La ciencia de qué documentar |
| 07 | [Process Antipatterns](./07-process-antipatterns.md) | Antipatrones de proceso |
| 08 | [Roadmap](./08-roadmap.md) | Hallazgos pendientes priorizados |
| 09 | [Metrics](./09-metrics.md) | Métricas de salud del vault |
| 10 | [Appendices](./10-appendices.md) | ISO standards, glosario |

### Metadata

- **Vault version:** {version}
- **Generated at:** {utcnow()}
- **Skill:** vault-sdd-init v1.0
- **Total documents:** 14

---

## EN

### Index

| # | Document | Description |
|---|---|---|
| 00 | [Principles](./00-principles.md) | Fundamental principles of the vault |
| 01 | [State Machines](./01-state-machines.md) | Lifecycle states per domain |
| 02 | [Implementation Guide](./02-implementation.md) | Guide for tool authors |
| 03 | [Usage Guide](./03-usage.md) | Guide for consumers |
| 04 | [Antipatterns](./04-antipatterns.md) | AP-01..AP-25 catalog |
| 05 | [Reference Matrix](./05-reference-matrix.md) | Pattern → Detect → Fix → Prevent |
| 06 | [Documentation Methodology](./06-documentation-methodology.md) | The science of what to document |
| 07 | [Process Antipatterns](./07-process-antipatterns.md) | Process antipatterns |
| 08 | [Roadmap](./08-roadmap.md) | Prioritized pending findings |
| 09 | [Metrics](./09-metrics.md) | Vault health metrics |
| 10 | [Appendices](./10-appendices.md) | ISO standards, glossary |

### Metadata

- **Vault version:** {version}
- **Generated at:** {utcnow()}
- **Skill:** vault-sdd-init v1.0
- **Total documents:** 14
"""


def generate_principles(vault_root: Path, drift: dict) -> str:
    """Generate 00-principles.md (bilingual)."""
    return f"""# Principios — Principles

> Documento bilingüe. Cada principio aparece primero en español, luego en inglés.
> Bilingual document. Each principle appears first in Spanish, then in English.

---

## ES

### 1. Idempotencia
Toda operación del vault debe ser re-ejecutable sin efectos colaterales.
- Mecanismos: `id` UUID estable en frontmatter, hash estable excluyendo campos volátiles.
- Garantía: reindex 2× produce mismo resultado.
- Detección: `vault_id_check.py`.

### 2. Trazabilidad
- Cadena de custodia: `id` + `createdAt` + `updatedAt` + `agent` + `migratedFrom`.
- Cada cambio → `vault_change_log` con `agent`.

### 3. Observabilidad
- Logs: `.tool-trace.json` (cap 500) + `.tool-tokens.json` (cap 2000).
- Métricas: `healthScore`, `dqHealth`, `tag_health`.

### 4. Versionado
- 5 capas: nota (`id` + `.history/`) → vault (`hash-index.json`) → tool (`tool-spec.json`) → estándar (`standard-version.json`) → changelog.

### 5. Seguridad de concurrencia
- **Regla**: Todo JSON index con read-modify-write DEBE usar `file_lock`.

### 6. Calidad de contenido
- Content gate: ≥3 líneas, ≥10 palabras, sin minified, sin path-anchored.
- DQ score per-note.
- `norm_refs` auto-embed.

### 7. Spec-First Development
- Editar `tool-spec.json` ANTES del código.
- `vault_spec_validate --strict` como CI gate.

### 8. Seguridad
- `vault_secret_scan` hook en `atomic_write_text` (v36).
- CIA values enforced.

### 9. Extensibilidad
- Skills como notas en `00_System/skills/`.
- Norms como código en `vault_norms.py`.

---

## EN

### 1. Idempotency
Every vault operation must be re-executable without side effects.
- Mechanisms: stable UUID `id` in frontmatter, stable hash excluding volatile fields.
- Guarantee: reindex 2× produces same result.
- Detection: `vault_id_check.py`.

### 2. Traceability
- Chain of custody: `id` + `createdAt` + `updatedAt` + `agent` + `migratedFrom`.
- Every change → `vault_change_log` with `agent`.

### 3. Observability
- Logs: `.tool-trace.json` (cap 500) + `.tool-tokens.json` (cap 2000).
- Metrics: `healthScore`, `dqHealth`, `tag_health`.

### 4. Versioning
- 5 layers: note (`id` + `.history/`) → vault (`hash-index.json`) → tool (`tool-spec.json`) → standard (`standard-version.json`) → changelog.

### 5. Concurrency Safety
- **Rule**: Every JSON index with read-modify-write MUST use `file_lock`.

### 6. Content Quality
- Content gate: ≥3 lines, ≥10 words, no minified, no path-anchored.
- DQ score per-note.
- `norm_refs` auto-embed.

### 7. Spec-First Development
- Edit `tool-spec.json` BEFORE code.
- `vault_spec_validate --strict` as CI gate.

### 8. Security
- `vault_secret_scan` hook in `atomic_write_text` (v36).
- CIA values enforced.

### 9. Extensibility
- Skills as notes in `00_System/skills/`.
- Norms as code in `vault_norms.py`.
"""


def generate_state_machines(vault_root: Path, drift: dict) -> str:
    """Generate 01-state-machines.md (bilingual)."""
    return """# State Machines — Máquinas de Estado

> Documento bilingüe. ES arriba, EN abajo.
> Bilingual document. ES above, EN below.

---

## ES

### Catálogo maestro de lifecycles

| Lifecycle | Estados | Tool |
|---|---|---|
| **Nota (Note)** | active / archived / deleted | vault_change_log |
| **Patrón (Pattern)** | planificado / en_progreso / implementado / deprecado / refactoring | vault_pattern_save |
| **Requisito (Requirement)** | draft / reviewed / approved / implemented / verified / obsolete | vault_requirement_save |
| **Test** | not_run / pass / fail / blocked / skip | vault_test_save |
| **Runbook execution** | success / failed / partial | vault_runbook_log |
| **Incidente (Incident)** | detected / investigating / identified / mitigating / resolved / closed / post-mortem | vault_incident_save |
| **SLO burn** | healthy / 1h-burn / 6h-burn / 30d-burn / breached | vault_slo_save |
| **Risk treatment** | accept / mitigate / transfer / avoid | vault_risk_save |
| **NCR** | open / closed | vault_ncr_save |
| **Backup** | active / superseded | (manual) |
| **Propagation pending** | pending / reviewed | vault_propagate |
| **Tool lifecycle** | active / deprecated / internal / meta / removed | tool-spec.json |
| **Standard version** | v19 → v20 → … → v36 | vault_standard_upgrade |

### Vocabulario unificado

- Los nombres canónicos son los listados arriba.
- Aliases comunes (EN/ES) se aceptan en escritura pero se normalizan en auditoría.

---

## EN

### Master lifecycle catalog

| Lifecycle | States | Tool |
|---|---|---|
| **Note** | active / archived / deleted | vault_change_log |
| **Pattern** | planificado / en_progreso / implementado / deprecado / refactoring | vault_pattern_save |
| **Requirement** | draft / reviewed / approved / implemented / verified / obsolete | vault_requirement_save |
| **Test** | not_run / pass / fail / blocked / skip | vault_test_save |
| **Runbook execution** | success / failed / partial | vault_runbook_log |
| **Incident** | detected / investigating / identified / mitigating / resolved / closed / post-mortem | vault_incident_save |
| **SLO burn** | healthy / 1h-burn / 6h-burn / 30d-burn / breached | vault_slo_save |
| **Risk treatment** | accept / mitigate / transfer / avoid | vault_risk_save |
| **NCR** | open / closed | vault_ncr_save |
| **Backup** | active / superseded | (manual) |
| **Propagation pending** | pending / reviewed | vault_propagate |
| **Tool lifecycle** | active / deprecated / internal / meta / removed | tool-spec.json |
| **Standard version** | v19 → v20 → … → v36 | vault_standard_upgrade |

### Unified vocabulary

- Canonical names are those listed above.
- Common aliases (EN/ES) are accepted on write but normalized on audit.
"""


def generate_implementation(vault_root: Path, drift: dict) -> str:
    """Generate 02-implementation.md."""
    return """# Implementation Guide — Guía de Implementación

> ES arriba, EN abajo. Bilingual.

---

## ES

### 1. Añadir nueva tool

1. Declarar en `scripts/tool-spec.json` con `required_args`, `declared_returns`,
   `dq_dimensions`, `fundamentals`, `status: active`.
2. Crear script usando `wrap_main` (logging automático).
3. Usar primitivos de `vault_io`: `atomic_write_text`, `file_lock`, `atomic_update_json`.
4. Si modifica JSON index → usar `file_lock`.
5. Si crea nota → usar `vault_write` (NO `write_text` directo).
6. Documentar en `scripts/README.md` con ejemplo.
7. Añadir test mínimo.
8. Correr `vault_spec_validate --strict`.

### 2. Matriz de file_lock

| Archivo | Lock timeout | Estado |
|---|---|---|
| `00_System/.tool-trace.json` | 5s | ✅ |
| `00_System/.change-log.json` | 5s | ⚠️ falta |
| `00_System/propagation-queue.json` | 30s | ✅ |
| `00_System/quality-index.json` | 30s | ✅ |
| `09_Infrastructure/.infra-index.json` | 10s | ✅ (v36) |
| `99_Index/search-index.json` | via atomic_update_json | ✅ |

### 3. Garantías de atomic_write

`atomic_write_text(path, content)`:
- Usa temp-file + `os.replace` (atómico en POSIX y Windows).
- En error → cleanup del temp file (v36 fix).
- Auto-triggers `_auto_section_index` post-write.
- Pre-write: secret scan via `vault_secret_scan.vault_write_hook` (v36).

### 4. Convención de error catalog

`vault_errors.ERROR_CATALOG` define códigos canónicos. Toda tool usa
`emit_error(tool, code, severity, message)` para reportar fallos.

---

## EN

### 1. Add new tool

1. Declare in `scripts/tool-spec.json` with `required_args`, `declared_returns`,
   `dq_dimensions`, `fundamentals`, `status: active`.
2. Create script using `wrap_main` (automatic logging).
3. Use `vault_io` primitives: `atomic_write_text`, `file_lock`, `atomic_update_json`.
4. If modifying JSON index → use `file_lock`.
5. If creating note → use `vault_write` (NOT `write_text` direct).
6. Document in `scripts/README.md` with example.
7. Add minimum test.
8. Run `vault_spec_validate --strict`.

### 2. file_lock matrix

(See table above in ES section.)

### 3. atomic_write guarantees

(See description above in ES section.)

### 4. Error catalog convention

`vault_errors.ERROR_CATALOG` defines canonical codes. Every tool uses
`emit_error(tool, code, severity, message)` to report failures.
"""


def generate_usage(vault_root: Path, drift: dict) -> str:
    """Generate 03-usage.md."""
    return """# Usage Guide — Guía de Uso

> ES arriba, EN abajo.

---

## ES

### 1. Protocolo de sesión

1. Inicializar: `vault_init` (crea estructura)
2. Crear notas: `vault_write --folder <X> --title <T> --content <C>`
3. Auditar: `vault_audit`
4. Reindexar: `vault_reindex --graph`
5. Backup: `vault_backup`

### 2. Contrato de frontmatter

Required: `id`, `title`, `createdAt`, `updatedAt`, `agent`
CIA: enum values `high`, `medium`, `low`
`norm_refs`: auto-embedded por folder + content matching

### 3. Wiki-links

- Stem-only: `[[note-name]]`
- AP-22: no `[[]]` vacíos
- AP-24: brackets balanceados
- AP-21: NO `[[folder/note]]`

### 4. Index / Search

- `99_Index/search-index.json` keyed por `id` (estable)
- `99_Index/hash-index.json` keyed por `id`, hash excluye `updatedAt`

### 5. Backup / Restore

- `vault_backup` → snapshot completo + Merkle root
- `vault_restore --backup <name>` → copia + `vault_reindex --graph`

---

## EN

### 1. Session protocol

(See ES section above.)

### 2. Frontmatter contract

(See ES section above.)

### 3. Wiki-links

(See ES section above.)

### 4. Index / Search

(See ES section above.)

### 5. Backup / Restore

(See ES section above.)
"""


def generate_antipatterns(vault_root: Path, drift: dict) -> str:
    """Generate 04-antipatterns.md with all 25 APs from NORM_CATALOG."""
    try:
        from vault_norms import NORM_CATALOG

        aps = [n for n in NORM_CATALOG if n.get("code", "").startswith("AP-")]
    except Exception:
        aps = []

    ap_md_es = []
    ap_md_en = []
    for ap in sorted(aps, key=lambda n: n["code"]):
        code = ap["code"]
        name = ap.get("name", "")
        desc = ap.get("description", "")
        severity = ap.get("severity", "")
        enforcement = ap.get("enforcement", "")
        prevention = ap.get("prevention", "")
        tools_detecting = ap.get("tools_detecting", [])

        ap_md_es.append(
            f"### {code}: {name}\n\n"
            f"- **Severidad:** {severity}\n"
            f"- **Enforcement:** {enforcement}\n"
            f"- **Detectado por:** {', '.join(tools_detecting) if tools_detecting else 'manual'}\n\n"
            f"{desc}\n\n"
            f"**Prevención:** {prevention}\n"
        )
        ap_md_en.append(
            f"### {code}: {name}\n\n"
            f"- **Severity:** {severity}\n"
            f"- **Enforcement:** {enforcement}\n"
            f"- **Detected by:** {', '.join(tools_detecting) if tools_detecting else 'manual'}\n\n"
            f"{desc}\n\n"
            f"**Prevention:** {prevention}\n"
        )

    header = f"""# Antipatterns — Antipatrones

> Documento bilingüe. Catálogo completo de AP-01..AP-{len(aps):02d} del vault.
> Bilingual document. Full AP-01..AP-{len(aps):02d} catalog.

---

## ES

Total de antipatrones registrados: {len(aps)}

"""
    footer_es = (
        "\n---\n\n## EN\n\nTotal registered antipatterns: " + str(len(aps)) + "\n\n"
    )
    return header + "\n".join(ap_md_es) + footer_es + "\n".join(ap_md_en)


def generate_reference_matrix(vault_root: Path, drift: dict) -> str:
    """Generate 05-reference-matrix.md."""
    return """# Reference Matrix — Matriz de Referencia

> Tabla cross-reference: antipatrón → herramienta que detecta → herramienta que arregla.
> Cross-reference table: antipattern → detecting tool → fixing tool.

---

## ES

| Antipattern | Detecta | Arregla | Previene |
|---|---|---|---|
| AP-11 Skeleton files | vault_validate | vault_write (re-create) | content gate |
| AP-13 Timestamps inválidos | vault_audit | vault_write (regenera) | frontmatter schema |
| AP-14 Wiki-links rotos | vault_audit --broken-links | (manual) | SP-02 forward-link verification |
| AP-17 Canonical-shadow | vault_audit | vault_deduplicate | vault_code_module AP-17 guard |
| AP-18 Cross-folder dup | vault_audit | vault_deduplicate | migration idempotent |
| AP-21 Path-anchored links | vault_write (guard) | vault_write (reject) | content gate |
| AP-22 Empty wikilinks | vault_write (guard) | vault_write (reject) | content gate |
| AP-23 Note > 500 lines | vault_write (advisory) | (manual split) | guidelines |
| AP-24 Bracket imbalance | vault_write (guard) + vault_audit | vault_render_check --fix | content gate |
| AP-25 Mermaid errors | vault_audit + vault_mermaid_check | (manual) | vault_mermaid_check |

---

## EN

| Antipattern | Detects | Fixes | Prevents |
|---|---|---|---|
| AP-11 Skeleton files | vault_validate | vault_write (re-create) | content gate |
| AP-13 Invalid timestamps | vault_audit | vault_write (regenerate) | frontmatter schema |
| AP-14 Broken wiki-links | vault_audit --broken-links | (manual) | SP-02 forward-link verification |
| AP-17 Canonical-shadow | vault_audit | vault_deduplicate | vault_code_module AP-17 guard |
| AP-18 Cross-folder dup | vault_audit | vault_deduplicate | migration idempotent |
| AP-21 Path-anchored links | vault_write (guard) | vault_write (reject) | content gate |
| AP-22 Empty wikilinks | vault_write (guard) | vault_write (reject) | content gate |
| AP-23 Note > 500 lines | vault_write (advisory) | (manual split) | guidelines |
| AP-24 Bracket imbalance | vault_write (guard) + vault_audit | vault_render_check --fix | content gate |
| AP-25 Mermaid errors | vault_audit + vault_mermaid_check | (manual) | vault_mermaid_check |
"""


def generate_methodology(vault_root: Path, drift: dict) -> str:
    """Generate 06-documentation-methodology.md (bilingual, the 'science')."""
    return """# Documentation Methodology — Metodología de Documentación

> ES arriba, EN abajo. Reglas duras para frontmatter, guidelines para contenido.

---

## ES

### Principios de documentación científica

**Principio 1: Trazabilidad atómica** — Toda declaración debe ser verificable.
- Cita: número de línea, path, hash.
- Cada "norma" tiene enforcing tool + detecting tool.

**Principio 2: Reversibilidad** — Toda modificación debe ser reversible.
- Toda escritura crea history snapshot.
- Toda eliminación usa change_log antes.
- Toda migración tiene rollback documented.

**Principio 3: Consistencia temporal** — El vault en T₀ + operación = vault en T₁.
- Idempotencia garantiza esto.
- Hash estable permite verificación.

**Principio 4: Granularidad apropiada** — No más, no menos.
- Una nota = un concepto.
- Una sección = un dominio.
- Una carpeta = un lifecycle.

**Principio 5: Conectividad explícita** — Las relaciones son first-class.
- Wiki-links como tejido conectivo.
- `relacionado_con:` en frontmatter cuando aplica.
- Cross-references en lugar de duplicación.

**Principio 6: Evolución documentada** — Cada cambio tiene historia.
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
"""


def generate_process_antipatterns(vault_root: Path, drift: dict) -> str:
    """Generate 07-process-antipatterns.md."""
    return """# Process Antipatterns — Antipatrones de Proceso

> ES arriba, EN abajo.

---

## ES

### SP-01: Delete sin change_log

**Síntoma**: Nota eliminada que no aparece en `.change-log.json`.

**Prevención**: Antes de eliminar, llamar `vault_change_log --action deleted`.

### SP-02: Linkar sin verificar

**Síntoma**: `[[nombre]]` que apunta a nota inexistente.

**Prevención**: `vault_search(query='nombre')` antes de linkar.

### SP-03: Sin snapshot antes de operaciones masivas

**Síntoma**: Cambios sin backup previo, errores irreversibles.

**Prevención**: `vault_backup` antes de operaciones masivas.

### SP-04 (nuevo): Modificar .md directamente (v36)

**Síntoma**: Notas editadas fuera de `vault_write`, sin secret scan.

**Prevención**: Toda edición de `.md` debe pasar por `vault_write`.

### SP-05 (nuevo): Pre-commit sin CI gate (v36)

**Síntoma**: Cambios sin validación automática.

**Prevención**: `.github/workflows/vault-ci.yml` corre en cada PR.

---

## EN

### SP-01: Delete without change_log

(See ES section above.)

### SP-02: Linking without verification

(See ES section above.)

### SP-03: No snapshot before mass operations

(See ES section above.)

### SP-04 (new): Direct .md modification (v36)

(See ES section above.)

### SP-05 (new): Pre-commit without CI gate (v36)

(See ES section above.)
"""


def generate_roadmap(vault_root: Path, drift: dict) -> str:
    """Generate 08-roadmap.md with prioritized findings."""
    return f"""# Roadmap — Hoja de Ruta

> Hallazgos pendientes priorizados. Severity-based.
> Pending findings prioritized. Severity-based.

---

## ES

Total de hallazgos documentados en auditoría 2026-06-28: 85+

### Críticos (en curso)

- ✅ A2/A3: AP-24, AP-25 registrados en NORM_CATALOG
- ✅ A1: Versión triple sincronizada en v36.0
- ✅ B1: atomic_write_text temp leak fixed
- ✅ C1/C2: Trace files unificados en 00_System/
- ✅ F1/F2: CI + 132 tests passing
- ✅ I1/I5: Secret scanning integrado en atomic_write_text

### Pendientes (próximas fases)

| ID | Severidad | Descripción |
|---|---|---|
| D2 | HIGH | Hotfix path undocumented |
| D3 | HIGH | vault_init --clean no backup before wipe |
| D4 | MEDIUM | Version detection by folder heuristic is fragile |
| G1 | HIGH | No guidance for concurrent users |
| G2 | HIGH | No fork-and-modify scenario guidance |
| H1 | HIGH | No vault_undo tool |
| H2 | HIGH | --dry-run only on 12 of 94 scripts |
| H6 | MEDIUM | Missing common commands (vault_delete, vault_rename, etc.) |
| J1 | HIGH | No plugin/extension system |
| J3 | HIGH | NORM_CATALOG not externally extendable |
| K3 | HIGH | Two slugify implementations (25+ duplicates) |
| K4 | HIGH | utcnow duplicated in 15+ scripts |

---

## EN

Total findings documented in audit 2026-06-28: 85+

### Critical (in progress)

(See list above in ES section.)

### Pending (next phases)

(See table above in ES section.)
"""


def generate_metrics(vault_root: Path, drift: dict) -> str:
    """Generate 09-metrics.md."""
    return """# Metrics — Métricas

> ES arriba, EN abajo.

---

## ES

### Métricas de salud del vault

| Métrica | Rango | Fuente | Significado |
|---|---|---|---|
| **healthScore** | 0-100 | vault_audit | Salud agregada del vault (penalizaciones) |
| **dqHealth.overall_dq_score** | 0-1 | vault_quality_check | Calidad de datos agregada |
| **dqHealth.notes_below_07** | int | vault_quality_check | Notas con DQ < 0.7 |
| **tag_health_score** | 0-100 | vault_audit | Salud del tag registry |
| **orphan_count** | int | vault_graph | Notas sin relaciones |
| **broken_link_count** | int | vault_audit --broken-links | Links a notas inexistentes |
| **mermaid_error_count** | int | vault_mermaid_check | Errores de sintaxis Mermaid |
| **render_error_count** | int | vault_render_check | Errores de render markdown (AP-26) |
| **idempotency_score** | 0-100 | (v36 nuevo) | Cobertura de file_lock + atomic_write |
| **trace_coverage** | % | (v36 nuevo) | % ops con trace entry |
| **secret_findings** | int | vault_secret_scan | Secretos detectados bloqueados |

### Umbrales recomendados

- healthScore >= 80: OK
- healthScore 50-79: warning
- healthScore < 50: critical

---

## EN

### Vault health metrics

(See table above in ES section.)

### Recommended thresholds

(See list above in ES section.)
"""


def generate_appendices(vault_root: Path, drift: dict) -> str:
    """Generate 10-appendices.md."""
    return """# Appendices — Apéndices

> ES arriba, EN abajo.

---

## ES

### A. Tool reference
Delegate a `scripts/README.md` (declarado en `scripts/tool-spec.json`).

### B. Norm reference
Delegate a `scripts/vault_norms.py` `NORM_CATALOG`.

### C. Spec-memory schema
`00_System/spec-memory.json` (auto-generado por vault_spec_memory).

### D. ISO standards map

| Estándar | Aplicación |
|---|---|
| ISO/IEC 25010 | Data quality (DQ dimensions) |
| ISO/IEC 12207 | Software lifecycle |
| ISO/IEC 14721 | OAIS (reference model for archives) |
| ISO/IEC 27001 | Information security |
| ISO/IEC 42001 | AI management |
| ISO 9001 | Quality management |

### E. Glosario bilingüe

| ES | EN |
|---|---|
| Antipatrón | Antipattern |
| Estado | State |
| Transición | Transition |
| Bloqueante | Blocking |
| Advertencia | Warning |
| Trazabilidad | Traceability |
| Idempotencia | Idempotency |
| Versionado | Versioning |
| Observabilidad | Observability |
| Auditoría | Audit |
| Lint | Lint |
| Plantilla | Template |
| Andamiaje | Scaffold |
| Estándar | Standard |
| Catálogo | Catalog |
| Referencia canónica | Canonical reference |
| Sombra | Shadow |
| Duplicado | Duplicate |
| Huérfano | Orphan |
| Roto | Broken |

---

## EN

### A. Tool reference
Delegate to `scripts/README.md` (declared in `scripts/tool-spec.json`).

### B. Norm reference
Delegate to `scripts/vault_norms.py` `NORM_CATALOG`.

### C. Spec-memory schema
`00_System/spec-memory.json` (auto-generated by vault_spec_memory).

### D. ISO standards map

(See table above in ES section.)

### E. Bilingual glossary

(See table above in ES section.)
"""


def generate_integrity_report(
    vault_root: Path, drift: dict, generated_files: list
) -> dict:
    """Generate integrity-report.json content."""
    return {
        "ok": True,
        "tool": "vault_sdd_init",
        "skill_version": "1.0",
        "vault_version": drift.get("version", "unknown"),
        "generated_at": utcnow(),
        "generated_files": generated_files,
        "expected_files": EXPECTED_OUTPUTS,
        "missing_files": [f for f in EXPECTED_OUTPUTS if f not in generated_files],
        "drift": drift,
        "checks_passed": len(drift.get("missing_norms", [])) == 0,
        "warnings": drift.get("warnings", []),
    }


def generate_gaps_md(vault_root: Path, drift: dict) -> str:
    """Generate gaps.md with prioritized findings."""
    return f"""# Gaps — Brechas Detectadas

> Lista priorizada de brechas detectadas durante la generación del SDD.
> Esta lista se actualiza con cada ejecución de la skill.

---

## ES

### Generado: {utcnow()}

### Drift detectado

- **Versión del vault:** {drift.get("version", "unknown")}
- **Normas faltantes:** {len(drift.get("missing_norms", []))}
- **Warnings:** {len(drift.get("warnings", []))}

### Hallazgos abiertos

Ver [08-roadmap.md](./08-roadmap.md) para la lista priorizada completa.

### Acciones manuales requeridas

1. Revisar y completar los schemas canónicos en [06-documentation-methodology.md](./06-documentation-methodology.md).
2. Revisar y aprobar los state machines en [01-state-machines.md](./01-state-machines.md).
3. Validar la reference matrix en [05-reference-matrix.md](./05-reference-matrix.md).
4. Cerrar los hallazgos críticos del [08-roadmap.md](./08-roadmap.md).

---

## EN

### Generated: {utcnow()}

### Detected drift

(See ES section above.)

### Open findings

See [08-roadmap.md](./08-roadmap.md) for full prioritized list.

### Required manual actions

(See list above in ES section.)
"""


GENERATORS = {
    "README.md": generate_readme,
    "00-principles.md": generate_principles,
    "01-state-machines.md": generate_state_machines,
    "02-implementation.md": generate_implementation,
    "03-usage.md": generate_usage,
    "04-antipatterns.md": generate_antipatterns,
    "05-reference-matrix.md": generate_reference_matrix,
    "06-documentation-methodology.md": generate_methodology,
    "07-process-antipatterns.md": generate_process_antipatterns,
    "08-roadmap.md": generate_roadmap,
    "09-metrics.md": generate_metrics,
    "10-appendices.md": generate_appendices,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault-sdd-init — Generate SDD documentation for the vault",
    )
    parser.add_argument(
        "--bilingual", action="store_true", help="Generate ES + EN content"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show plan without writing"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force regeneration (bypass idempotency)"
    )
    parser.add_argument(
        "--vault-root",
        default=str(VAULT_ROOT),
        help="Vault root path (default: auto-detect)",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault_root).resolve()
    sdd_dir = vault_root / SDD_OUTPUT_DIR

    print(f"vault-sdd-init v1.0")
    print(f"Vault: {vault_root}")
    print(f"Output: {sdd_dir}")
    print(f"Bilingual: {args.bilingual}")
    print(f"Dry-run: {args.dry_run}")
    print()

    drift = detect_drift(vault_root)
    print(f"Drift detected:")
    print(f"  Version: {drift['version']}")
    print(f"  Missing norms: {len(drift['missing_norms'])}")
    print(f"  Warnings: {len(drift['warnings'])}")
    print()

    if args.dry_run:
        print("DRY RUN: would generate the following files:")
        for fname in EXPECTED_OUTPUTS:
            target = sdd_dir / fname
            print(f"  {target}")
        print()
        print("No files written.")
        return 0

    sdd_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for fname, generator in GENERATORS.items():
        target = sdd_dir / fname
        content = generator(vault_root, drift)
        atomic_write_text(target, content)
        generated.append(fname)
        print(f"  [OK] {fname}")

    # After all MD files are written, generate integrity + gaps
    integrity = generate_integrity_report(
        vault_root, drift, generated + ["integrity-report.json", "gaps.md"]
    )
    atomic_write_json(sdd_dir / "integrity-report.json", integrity)
    print(f"  [OK] integrity-report.json")

    gaps_content = generate_gaps_md(vault_root, drift)
    gaps_path = sdd_dir / "gaps.md"
    if gaps_path.exists() and not args.force:
        existing = gaps_path.read_text(encoding="utf-8")
        if "# Gaps" not in existing or len(existing) < 200:
            atomic_write_text(gaps_path, gaps_content)
            print(f"  [OK] gaps.md (updated)")
        else:
            print(f"  [SKIP] gaps.md (preserved - manual content detected)")
    else:
        atomic_write_text(gaps_path, gaps_content)
        print(f"  [OK] gaps.md")

    print()
    print(f"Generated {len(generated) + 2} files in {sdd_dir}")
    print(f"Drift status: {'PASS' if integrity['checks_passed'] else 'WARN'}")
    if integrity["warnings"]:
        print(f"Warnings: {integrity['warnings']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
