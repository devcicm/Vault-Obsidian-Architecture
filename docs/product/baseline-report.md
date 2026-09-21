# Vault Obsidian Architecture — Productization Baseline Report

**Fecha:** 2026-09-20
**HEAD:** `f5ed8f4bad29f40e9137a07f5711848d9c891f89`
**Branch:** `main`
**Worktree principal:** `C:\Users\Carlos Ivan\Documents\GitHub\Vault-Obsidian-Architecture`

---

## Git State

| Dato | Valor |
|------|-------|
| HEAD | `f5ed8f4` |
| Branch | `main` |
| Worktrees activos | 1 (main) + 4 prunable (referencias rotas) |
| Worktrees prunable | `voa-pr02b-fixture-verify`, `voa-pr05-sandbox`, `voa-pr05-boundary`, `voa-pr05-recovery`, `voa-pr05-recovery-v2` |

### Dirty State

| Archivo | Cambio |
|---------|--------|
| `.gitignore` | Modified |
| `README.md` | Modified |
| `tests/dorados/saves/vault_ncr_save.json` | Modified |
| `tests/test_caracterizacion_de_los_save.py` | Modified |
| `tests/test_fix_all.py` | Modified |
| `vault-sandbox/00_System/tool-spec.json` | **Staged** (4351 líneas) |
| `docs/architecture/` | **Untracked** (nuevo directorio) |
| `docs/product/` | **Untracked** (nuevo directorio, 1 archivo: `overview.md`) |

### Ramas con trabajo previo no fusionado

| Rama | HEAD | Cambio vs main | Clasificación |
|------|------|----------------|--------------|
| `codex/pr-b-product-docs` | `ca0d284` | `overview.md` + `layers.md` + tests + README | **UNIQUE_VALID_CHANGE** — Documentos de producto legítima |
| `codex/pr-05-installable-boundary` | `5b08c5f` | `vault_toolkit/` (80+ módulos) + CLI resolver + distribución | **UNIQUE_VALID_CHANGE** — Motor de installed operations |
| `codex/pr-05-boundary-recovery-v2` | `3db34de` | `vault/product_cli.py` + ciclo_de_vida + kernel escritura + distribución | **UNIQUE_VALID_CHANGE** — Product CLI y lifecycle |

> **Decisión:** Las ramas `codex/` contienen trabajo de productización valioso y no deben descartarse. El plan las integra mediante merge antes de continuar.

---

## Inventario Técnico

### Versiones

| Dato | Valor |
|------|-------|
| TOOLKIT_VERSION | `40.34` (en `pyproject.toml`) |
| STANDARD_VERSION | `v40.34` (en `scripts/vault_version.py`) |
| RUNTIME_SCHEMA | No declarado (no existe separación) |
| **VERSION_MODEL** | **COUPLED** — toolkit, standard y schema están juntos |

### Python y Dependencias

| Dato | Valor |
|------|-------|
| requires-python | `>=3.9` |
| Dependencias | `PyYAML>=6.0` |
| Optional deps | `dev = pytest>=7.0, pytest-cov>=4.0, ruff>=0.3.0` |
| CI Python matrix | `3.9`, `3.11` (solo estos dos) |
| CI OS matrix | `ubuntu-latest`, `windows-latest` |

### Tools y Scripts

| Dato | Valor |
|------|-------|
| TOTAL_TOOLS | **116** |
| RUNTIME_TOOLS | **0** — no existen operaciones instaladas reales |
| META_TOOLS | **0** — no hay distinción |
| SCRIPT_MODULES | **152** (`scripts/vault_*.py`) |
| STABLE_MODULES | **33** (`vault/**/*.py` excluyendo `__pycache__`) |
| **REAL_INSTALLED_OPERATIONS** | **0** |
| **LEGACY_ONLY_RUNTIME_OPERATIONS** | **116** — todas las tools son scripts |

### Arquitectura stable dentro de `vault/`

```
vault/
├── autoria/           (frontmatter.py, repositorio.py)
├── ciclo_de_vida/     (repositorio.py) — vacío funcionalmente
├── consulta/         (repositorio.py) — vacío funcionalmente
├── durabilidad/      (cuarentena.py, modelo.py, restauracion.py, snapshot.py)
├── gobernanza/       (repositorio.py) — SIN GobernanzaBase, SIN overrides
├── grafo/            (repositorio.py) — vacío funcionalmente
├── indices/          (carpetas.py, coherencia.py, enumeracion.py, maestro.py,
│                       reconstruccion.py, repositorio.py, seccion.py)
├── kernel/           (adaptadores.py, contexto.py, fallos.py, puertos.py)
└── meta_toolkit/     (repositorio.py) — vacío funcionalmente
```

**No existe:**
- `vault_toolkit/` — absent in main, existe en `codex/pr-05-installable-boundary`
- `vault/gobernanza/base.py` — absent
- `vault/gobernanza/cli_gobernanza.py` — absent
- `vault/gobernanza/mcp_gobernanza.py` — absent
- `vault/ciclo_de_vida/producto.py` — absent in main, existe en `codex/pr-05-boundary-recovery-v2`
- `vault/meta_toolkit/distribucion.py` — absent in main, existe en `codex/pr-05-*`
- `vault/product_cli.py` — absent in main, existe en `codex/pr-05-boundary-recovery-v2`

---

## Gates y Suite

| Dato | Valor |
|------|-------|
| Gates totales | 22 |
| Gates passing | 22 |
| Gates failing | 0 |
| Tiempo gates | 44.18s |
| Tests recolectados | 3093 |
| Tests files | 136 (`test_*.py`) |

### Promise Registry (vault_produccion.py)

| Promesa | Estado | Ejercida |
|---------|--------|----------|
| piso_de_lenguaje | cubierta | sí |
| dependencias_reales | cubierta | sí |
| instalacion_fuera_del_repo | cubierta | sí |
| material_ajeno | cubierta | sí |
| sistemas_operativos | cubierta | sí (con hueco: macOS no testado) |
| superficie_expuesta | cubierta | sí |
| ergon_de_entrada | **descubierta** | **NO** — decisión de producto pendiente |
| contrato_con_quien_contribuye | cubierta | sí |
| lo_publicado_es_solo_el_estandar | cubierta | sí (con hueco conocido) |

**Descubiertas:** 1 (`ergon_de_entrada`)

### Pre-commit Hook

| Dato | Valor |
|------|-------|
| Ubicación actual | `.git/hooks/pre-commit` (legacy) |
| `.githooks/pre-commit` | No existe |
| `core.hooksPath` | No configurado |

> **Hueco:** El hook no resuelve correctamente en worktrees. Se propone configuración canónica en `.githooks/` con `core.hooksPath`.

---

## Migration Engine

| Dato | Valor |
|------|-------|
| Migration engine state | **NOT EXTRACTED** |
| Installed migration planner | No |
| Migration corpus | No |
| `vault_standard_upgrade` | Script legacy en `scripts/` |
| Migration registry | No existe |

---

## Compatibilidad

| Dato | Valor |
|------|-------|
| Compatibility manifest | **NO EXISTE** |
| Offline installation proven | **NO** |
| Python support matrix | **PARCIAL** (3.9, 3.11 en CI; 3.10, 3.12, 3.13, 3.14 no probados) |
| READ_WINDOW | No modelado |
| WRITE_WINDOW | No modelado |
| UNKNOWN_VERSION fails closed | No verificado |

---

## Producto y Subproductos

| Producto | Estado | Versión |
|----------|--------|---------|
| Estándar | Activo | v40.34 |
| Toolkit | Scripts only | Coupled to standard |
| CLI | Funcional (sin entry point público) | Coupled to standard |
| MCP | Funcional | Coupled to standard |
| Runtime (vault-sandbox) | Pruebas | — |

### docs/product/ — Estado

| Archivo | Estado |
|---------|--------|
| `docs/product/overview.md` | Existe (132 líneas, draft) — en `codex/pr-b-product-docs` |
| `docs/product/`其余 | No existe en main — contenido en branches `codex/` |

### docs/architecture/ — Estado

| Archivo | Estado |
|---------|--------|
| `docs/architecture/layers.md` | Existe (59 líneas) — unstaged |

---

## Métricas Globales — Estado Actual

| Métrica | Valor | Target |
|---------|-------|--------|
| LEGACY_ONLY_RUNTIME_OPERATIONS | 116 | 0 |
| REAL_INSTALLED_OPERATIONS | 0 | 116 |
| STABLE_TO_SCRIPTS_DEPENDENCIES | 0 (sin estable aún) | 0 |
| GLOBAL_SOURCE_CHECKOUT_DEPENDENCY | YES (todas las tools son scripts) | NO |
| TOOLKIT_STANDARD_VERSION_DECOUPLED | NO | YES |
| PYTHON_SUPPORT_MATRIX_PROVEN | NO | YES |
| DEPENDENCY_CONSTRAINTS_PROVEN | NO | YES |
| OFFLINE_INSTALLATION_PROVEN | NO | YES |
| INSTALLED_UPGRADE_ENGINE | NO | YES |
| UNKNOWN_VERSION_FAILS_CLOSED | NO | YES |
| FAILED_MIGRATION_NEVER_STAMPS | NO | YES |
| MIGRATION_ROLLBACK_PROVEN | NO | YES |
| MIGRATION_IDEMPOTENCE_PROVEN | NO | YES |
| OLD_RUNTIME_TO_LATEST_PROVEN | NO | YES |
| MARKDOWN_REMAINS_AUTHORITY | YES (no hay índice obligatorio) | YES |
| DERIVED_ARTIFACTS_REBUILDABLE | YES (scripts + vault_io) | YES |
| FULL_SUITE_PASSED | 3093 collected | 3093 |
| STRICT_GATES | 22/22 | 22/22 |
| GOLD_GATE | NOT RUN | PASS |
| DOGFOOD_VAULT_USED | NO | YES |
| DOGFOOD_CHECKPOINT_RECOVERY_PROVEN | NO | YES |
| WORKTREE_CLEAN | NO (dirty state) | YES |

---

## Clasificación del Trabajo Previo (codex/)

| Rama | Contenido | ¿Merge a main? | Orden |
|------|-----------|-----------------|-------|
| `codex/pr-b-product-docs` | `docs/product/overview.md`, `docs/architecture/layers.md` | **SÍ** | 1º |
| `codex/pr-05-installable-boundary` | `vault_toolkit/` (80+ módulos), CLI resolver, distribución | **SÍ** | 2º |
| `codex/pr-05-boundary-recovery-v2` | `vault/product_cli.py`, ciclo_de_vida, kernel escritura | **SÍ** | 3º |

---

## Producto Readyness Checklist

| # | Métrica | Estado actual |
|---|---------|---------------|
| 1 | LEGACY_ONLY_RUNTIME_OPERATIONS = 0 | **FAR** (116) |
| 2 | STABLE_TO_SCRIPTS_DEPENDENCIES = 0 | **N/A** (sin estables aún) |
| 3 | GLOBAL_SOURCE_CHECKOUT_DEPENDENCY = NO | **FAR** (YES) |
| 4 | TOOLKIT_STANDARD_VERSION_DECOUPLED = YES | **FAR** (NO) |
| 5 | PYTHON_SUPPORT_MATRIX_PROVEN = YES | **FAR** (NO) |
| 6 | DEPENDENCY_CONSTRAINTS_PROVEN = YES | **FAR** (NO) |
| 7 | OFFLINE_INSTALLATION_PROVEN = YES | **FAR** (NO) |
| 8 | INSTALLED_UPGRADE_ENGINE = YES | **FAR** (NO) |
| 9 | UNKNOWN_VERSION_FAILS_CLOSED = YES | **FAR** (NO) |
| 10 | FAILED_MIGRATION_NEVER_STAMPS = YES | **FAR** (NO) |
| 11 | MIGRATION_ROLLBACK_PROVEN = YES | **FAR** (NO) |
| 12 | MIGRATION_IDEMPOTENCE_PROVEN = YES | **FAR** (NO) |
| 13 | OLD_RUNTIME_TO_LATEST_PROVEN = YES | **FAR** (NO) |
| 14 | FULL_SUITE_PASSED | **PENDING** |
| 15 | STRICT_GATES = PASS | **GREEN** |
| 16 | GOLD_GATE = PASS | **FAR** |
| 17 | DOGFOOD_VAULT_USED = YES | **FAR** |
| 18 | DOGFOOD_CHECKPOINT_RECOVERY_PROVEN = YES | **FAR** |
| 19 | WORKTREE_CLEAN = YES | **FAR** (dirty) |

```
PRODUCT_READY = NO
```

---

## Siguiente Paso: CHECKPOINT 1

### EXACT_NEXT_CHECKPOINT

**Alcance:**

1. **Proteger dirty state** — guardar status, unstaged patches, staged patches
2. **Merge `codex/pr-b-product-docs` a main** — bring product docs
3. **Merge `codex/pr-05-installable-boundary` a main** — bring installed operations engine
4. **Merge `codex/pr-05-boundary-recovery-v2` a main** — bring product CLI and lifecycle
5. **Verificar gates post-merge** — `vault_gate --strict` + suite
6. **Generar checklist de GovernanceBase** — crear clase abstracta con los overrides CLI/MCP
7. **Guardar checkpoint en vault dogfood externo**

**Criterio de cierre:**
- `vault_gate --strict` → 22/22
- `python -m pytest tests/` → verde
- `vault/product_cli.py` existe y funciona
- `vault_toolkit/` con operaciones instaladas
- CHECKPOINT guardado en vault externo y recuperado en proceso nuevo
