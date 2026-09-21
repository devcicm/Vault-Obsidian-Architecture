# Vault Obsidian Architecture — Productization Baseline Report

**Fecha:** 2026-09-20
**HEAD post-merge:** `3db34de` (codex/pr-05-boundary-recovery-v2)
**Branch:** `main` (post-merge)

---

## Merge Log

| Paso | Rama | Resultado |
|------|------|-----------|
| 1 | `codex/pr-b-product-docs` | Fast-forward, OK |
| 2 | `codex/pr-05-installable-boundary` | Fast-forward, OK |
| 3 | `codex/pr-05-boundary-recovery-v2` | Conflictos resueltos (9 archivos) |

### Conflictos resueltos

| Archivo | Resolución |
|---------|-----------|
| `agents.md` | branch (3181 tests, más reciente) |
| `cli/registry.py` | branch (imports `distribution_metadata`) |
| `cli/resolver.py` | branch (lógica completa con validación) |
| `cli/runner.py` | branch (maneja `invalid` target kind) |
| `docs/ARQUITECTURA.md` | branch |
| `docs/BLUEPRINT.md` | branch |
| `scripts/vault_arch.py` | branch |
| `vault/autoria/frontmatter.py` | branch (`yaml_scalar` inline) |
| `vault/meta_toolkit/distribucion.py` | branch (validación `extras`) |

---

## Inventario Post-Merge

### Versiones

| Dato | Valor |
|------|-------|
| TOOLKIT_VERSION | `40.34` → `41.0` (en `pyproject.toml` tras merge) |
| STANDARD_VERSION | `v40.34` |
| RUNTIME_SCHEMA | `2` (nuevo, en `vault/ciclo_de_vida/runtime-seed.json`) |
| **VERSION_MODEL** | **DECOUPLED** — toolkit ≠ standard ≠ schema |

### Arquitectura Stable

```
vault/
├── autoria/          frontmatter.py, conocimiento.py, knowledge_get.py, knowledge_save.py, voz.py
├── ciclo_de_vida/   producto.py (nuevo), repositorio.py, runtime-seed.json
├── consulta/         query_parse.py (nuevo)
├── durabilidad/      cuarentena.py, modelo.py, restauracion.py, snapshot.py
├── gobernanza/      auditoria_runtime.py (nuevo), repositorio.py
├── grafo/           enlace_codigo.py (nuevo), repositorio.py
├── indices/         carpetas.py, coherencia.py, enumeracion.py, maestro.py, reconstruccion.py,
│                    repositorio.py, seccion.py, vocabulario.py (nuevo)
├── kernel/          adaptador es.py, contenido.py (nuevo), errores.py (nuevo),
│                    escritura.py (nuevo), fallos.py, puertos.py
└── meta_toolkit/   catalogo_producto.py (nuevo), distribucion.py, naturalezas.py (nuevo),
                     resolucion_producto.py (nuevo), recursos_distribucion.py

vault_toolkit/          (NUEVO — installed operations)
├── __init__.py
├── loading.py
└── operations/       (80+ módulos vault_*.py)
```

### nuevo en este merge

| Archivo/Directorio | Descripción |
|-------------------|-------------|
| `vault_toolkit/` | Módulo de installed operations |
| `vault/product_cli.py` | CLI de producto instalada |
| `vault/ciclo_de_vida/producto.py` | Ciclo de vida del producto |
| `vault/ciclo_de_vida/runtime-seed.json` | Runtime schema v2 |
| `vault/consulta/query_parse.py` | Query parser estable |
| `vault/gobernanza/auditoria_runtime.py` | Auditoría runtime |
| `vault/kernel/escritura.py` | Escritura gobernada |
| `vault/kernel/contenido.py` | Contenido estructurado |
| `vault/kernel/errores.py` | Errores del kernel |
| `vault/meta_toolkit/naturalezas.py` | Naturalezas de tools |
| `vault/meta_toolkit/catalogo_producto.py` | Catálogo de producto |
| `vault/meta_toolkit/resolucion_producto.py` | Resolución de producto |
| `vault/autoria/conocimiento.py` | Conocimiento documental |
| `vault/autoria/voz.py` | Voz del producto |
| `vault/grafo/enlace_codigo.py` | Enlace código-vault |
| `vault/indices/vocabulario.py` | Vocabulario indexed |
| `cli/resolver.py` | Resolver de operations |
| `.githooks/pre-commit` | Hook canónico |
| `docs/product/runtime-contract.md` | Contrato runtime |
| `docs/adr/0001-hybrid-toolkit-runtime-distribution.md` | ADR distribución |
| `scripts/vault_distribution_sync.py` | Sync de distribución |
| `tests/test_installable_boundary.py` | Test boundary |
| `tests/test_pre_commit_worktree.py` | Test pre-commit |
| `tests/clean_install_gate.py` | Gate instalación limpia |
| `tests/memory_recovery_e2e_gate.py` | Gate recovery e2e |
| `tests/runtime_lifecycle_gate.py` | Gate lifecycle |
| `tests/test_cli_resolver.py` | Test resolver |
| `tests/test_distribution_metadata.py` | Test distribución |
| `tests/test_installed_memory.py` | Test memoria instalada |
| `tests/test_installed_query_parse.py` | Test query parse |
| `tests/test_product_lifecycle.py` | Test lifecycle producto |
| `tests/test_public_cli.py` | Test CLI pública |

---

## Métricas Post-Merge

| Métrica | Antes | Después |
|---------|-------|---------|
| REAL_INSTALLED_OPERATIONS | 0 | 80+ (vault_toolkit/) |
| LEGACY_ONLY_RUNTIME_OPERATIONS | 116 | 36 (sin vault_toolkit/) |
| TOOLKIT_STANDARD_VERSION_DECOUPLED | NO | **SÍ** |
| VERSION_MODEL | COUPLED | DECOUPLED |
| GovernanceBase | NO EXISTE | parcial (auditoria_runtime.py) |
| Migration Engine | NOT EXTRACTED | en ciclo_de_vida/producto.py |

---

## Siguiente Paso: CHECKPOINT 1

**Estado:** Los 3 merges completados. Conflictos resueltos. Commit pendiente.

**Antes de CHECKPOINT 1:**
- Commit del merge
- Recrear baseline-report.md en docs/product/
- Verificar `vault_gate --strict`
- Verificar suite
- Crear rama `product/product-readiness`
- Implementar PRD, Roadmap, GobernanzaBase
