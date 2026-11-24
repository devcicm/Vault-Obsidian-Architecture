<!-- propiedad: CARLOS IVAN CM · revisión: manual · revisado: 2026-11-23 -->

# Mapa de Conteos, Registros y Assertions Fijadas

> Referencia rápida del repositorio estándar: ubica **dónde vive cada registro canónico**,
> **qué comando regenera lo derivado** y **qué archivos/tests fijan cantidades o listas explícitas**.
> Al agregar, quitar o modificar cualquier capacidad, consulta primero esta tabla para no dejar
> conteos ni contratos desfasados (AP-05 / AP-47).

## 1. Tabla operativa por tipo de cambio

| Qué cambiaste | Dueño canónico (fuente única) | Comando regenerador | Archivos / tests con lista o cifra fijada |
|---|---|---|---|
| **Tool nueva / modificada / parámetros CLI** | `scripts/vault_mcp_catalog.py` (`TOOLS_CATALOG`, `GROUPS`, `ACCESS_MODES`, `GLOBAL_SCOPE_TOOLS`) | `python scripts/vault_mcp_catalog.py --sync` · `python scripts/vault_esquema.py --sync` · `python scripts/vault_doc_sync.py --fix` · `python scripts/vault_doc_counts.py --fix` | `scripts/README.md`, `vault-sandbox/00_System/tool-spec.json`, `scripts/vault_arch.py` (`CONTEXTS`), `scripts/vault_servicio.py`. |
| **Parámetro de ruta externa (`"ruta": "externa"`, AP-36)** | `scripts/vault_mcp_catalog.py` (el nombre del param debe incluir `path`/`dir`/`file`/`folder`/`source`/`target`) | `python scripts/vault_mcp_catalog.py --sync` | `tests/test_preflight_rutas_externas.py` (`EXTERNAS_ESPERADAS`). |
| **Puerto público entre contextos** | `scripts/vault_arch.py` (`CONTEXTS[ctx]["puertos"]`) | `python scripts/vault_arch.py --blueprint` | `tests/test_puertos_verificados.py` (`assert len(PUERTOS) == ...`), `docs/ARQUITECTURA.md`. |
| **Contexto acotado o cruce entre contextos** | `scripts/vault_arch.py` (`CONTEXTS`, `PRESUPUESTO_DE_CRUCES`) | `python scripts/vault_arch.py --blueprint` | `tests/test_arquitectura_trazabilidad.py` (`assert len(fichas) == ...`), `scripts/arch-baseline.json`. |
| **Norma (`AP`/`PAT`/`SP`/`CN`)** | `normas/<código>/norma.py` + `porque.md` + `test_*.py` (`vault/kernel/normativa/norms_catalog.py`) | `vault_norms_engine.escribir_caras_derivadas` · `python scripts/vault_sdd_init.py --bilingual --force --vault-root .` · `python scripts/vault_doc_counts.py --fix` | `vault-obsidian-architecture.md`, `scripts/norms-coherence-baseline.json`, `scripts/norms-distincion-baseline.json`. |
| **Skill (`agent/skills/<nombre>/SKILL.md`)** | `agent/skills/<nombre>/SKILL.md` (`name`, `version`, `entry-point`) + script asociado | `python scripts/vault_doc_counts.py --fix` | `docs/SKILLS.md` (tabla + versiones archivadas `SKILL-v*.md`), `tests/test_skills_contract.py`, `tests/test_skills_versionadas.py`, `tests/test_skills_catalogo.py` (`SDD_CONSTANTES_BASELINE`). |
| **Variable de entorno (`VAULT_*`)** | `vault/kernel/entorno.py` (`VARIABLES`) | `python scripts/vault_arch.py --sync-env` · `python scripts/vault_entorno.py --doc` | `mcp/nodejs/`, `docs/ENTORNO.md`, `tests/test_registro_de_entorno.py`. |
| **Puerta de calidad o carril** | `scripts/vault_gate.py` (`PUERTAS`) · `vault/meta_toolkit/estandar/carriles.py` | `python scripts/vault_gate.py --fix-doc` · `python -m vault.meta_toolkit.estandar.carriles --doc` · `python scripts/vault_doc_counts.py --fix` | `AGENTS.md`, `docs/PUERTAS.md`, `docs/CARRILES.md`. |
| **Sección estándar del vault** | `vault/kernel/registry.py` (`SECTIONS`, `SECTION_DOCUMENTACION`) | `python scripts/vault_doc_counts.py --fix` | `tests/test_indices_dominio.py` (`len(repo.ctx.secciones.ordenadas())`), `docs/sdd/06-documentation-methodology.md`. |
| **Documento vivo nuevo en `docs/`** | `docs/<NOMBRE>.md` con cabecera `<!-- propiedad: CARLOS IVAN CM · revisión: manual · revisado: AAAA-MM-DD -->` | `python scripts/vault_doc_sync.py --check --strict` | `vault/kernel/registry.py` (`DOCS_DEL_REPO`), `docs/README.md`, `tests/test_propiedad_docs.py` (`DERIVADOS`). |
| **Versión del estándar** | `vault/kernel/version.py` (`CURRENT_VERSION`) | `python scripts/vault_changelog_check.py --fijar-hash` | `pyproject.toml`, `README.md`, `vault-obsidian-architecture.md`, `vault-sandbox/00_System/standard-version.json`, `tests/test_version_coherence.py`. |
| **Tests / bloques / perfil de lentos** | `tests/test_*.py` + `vault/meta_toolkit/estandar/inventario_tests.py` | `python scripts/vault_doc_counts.py --fix` · `python -m vault.meta_toolkit.estandar.perfil_suite --refrescar` | `AGENTS.md`, `tests/duraciones-por-modulo.json`, `scripts/tests-higiene-baseline.json`. |
| **Vocabularios y registros cerrados** | `STATUS_VOCAB`, `RELATION_TYPES`, `FRAMEWORK_REGISTRIES['iso_coverage']`, `PENALIZACIONES`, `FORMAS_DE_DOCUMENTO`, `CATALOGO_PATRONES` | `python scripts/vault_doc_counts.py --fix` | `tests/test_vault_relation_add.py`, `tests/test_vault_sdd_init.py` (`EXPECTED_OUTPUTS`), `tests/test_patrones_diseno_detector.py`, `tests/test_blindaje_deuda_fase_i.py`. |

## 2. Documentos vigilados automáticamente por `vault_doc_counts.py`

`README.md`, `AGENTS.md`, `cli/README.md`, `cli/COMMANDS.md`, `docs/SKILLS.md`, `mcp/PLAN.md`, `scripts/README.md`, `docs/product/overview.md` y `vault-obsidian-architecture.md`.

## 3. Baselines congeladas (`scripts/*-baseline.json`)

Todas las baselines **solo encogen** con `--freeze` (crecer exige `--freeze --admitir-nuevos` tras revisión):

`arch`, `blame`, `blueprint`, `ciclos`, `clones`, `criterios`, `error-contract`, `excepcion-declarada`, `field-compat`, `kernel`, `noop`, `norms-coherence`, `norms-distincion`, `recursos`, `rutas`, `smoke`, `tests-higiene` y `toolkit-audit`.

## 4. Cierre automatizado en una sola pasada

```bash
python scripts/vault_fix_all.py
python -m vault.meta_toolkit.estandar.corredor_suite --plan
python scripts/vault_gate.py --strict --nivel rapida
```
