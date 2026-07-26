# Implementation Guide -- Guía de Implementación

> ES arriba, EN abajo. Bilingual.

---

## ES

### 1. Añadir nueva tool

1. Declarar en `00_System/tool-spec.json` con `required_args`, `declared_returns`,
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

1. Declare in `00_System/tool-spec.json` with `required_args`, `declared_returns`,
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
