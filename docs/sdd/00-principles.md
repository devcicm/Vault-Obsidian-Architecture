# Principios -- Principles

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
