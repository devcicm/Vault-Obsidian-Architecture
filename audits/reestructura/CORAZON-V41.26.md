# El corazón de v41.26 — y de qué generación es cada cosa

Documento **generado**: `python audits/reestructura/generar_corazon.py`.
Ninguna cifra de aquí está escrita a mano (AP-47): todas salen del grafo
de imports, del registro de contextos y de las puertas del propio repo.

## 1. Qué es el corazón

El estándar ya tiene la medida (AP-59): un módulo del **núcleo** es el
que de él depende todo lo demás. El umbral de fan-in es
**80**, y el de fan-out **10**;
el churn no puede pasar de **20.31** (la mediana del
dominio es 15).

| Módulo | fan-in | fan-out | Papel |
|---|---:|---:|---|
| `vault_errors` | **141** | 5 | código real |
| `vault_io` | **108** | 10 | código real |
| `vault_lib` | **80** | 2 | código real |
| `vault_registry` | **44** | 2 | fachada |
| `vault_norms_catalog` | **37** | 1 | fachada |
| `vault_entorno` | **34** | 0 | fachada |
| `vault_encoding` | **28** | 2 | código real |
| `vault_grafo_import` | **26** | 0 | código real |
| `vault_vocabulario` | **21** | 2 | fachada |
| `vault_baseline` | **17** | 2 | fachada |
| `vault_regex` | **17** | 0 | código real |
| `vault_mcp_catalog` | **16** | 5 | código real |
| `vault_fundamentals_catalog` | **12** | 0 | fachada |
| `vault_subproceso` | **12** | 0 | código real |
| `vault_version` | **12** | 0 | fachada |
| `vault_contrato_nota` | **11** | 3 | fachada |

Con el umbral del propio estándar, el corazón son los módulos que
alcanzan fan-in ≥ 80: `vault_errors`, `vault_io`, `vault_lib`.

### Las tres capas

| Capa | Qué es | Dónde |
|---|---|---|
| **Superficie** | las tools que se publican y se ejecutan | `scripts/`: 115 tools |
| **Dueños** | los criterios, cada uno en su contexto | `vault/<contexto>/` |
| **Hojas** | lo que no depende de nadie | `vault/kernel/` |

## 2. Los hallazgos vivos sobre el núcleo

### `kernel_inestable` (3)

- `vault_errors`: 40 commits ≥ el escalón 20.31 del dominio (mediana 15): el núcleo debería moverse menos que lo que sostiene (valor: 40).
- `vault_io`: 63 commits ≥ el escalón 20.31 del dominio (mediana 15): el núcleo debería moverse menos que lo que sostiene (valor: 63).
- `vault_lib`: 27 commits ≥ el escalón 20.31 del dominio (mediana 15): el núcleo debería moverse menos que lo que sostiene (valor: 27).

### `kernel_impuro` (1)

- `vault_io`: fan-out 10 ≥ el escalón 10 del propio kernel: un módulo del que todos dependen y que depende de muchos propaga cada cambio hacia arriba (valor: 10).

## 3. `scripts/` en tres: tools, fachadas y los demás

- **Tools** (con `__main__`, se ejecutan): **115**
- **Fachadas** (alias a un dueño en `vault/`): **45**
- **Otros** (código real sin punto de entrada): **11**

### La tabla que no existía: cada fachada y su dueño

| Fachada en `scripts/` | Dueño real |
|---|---|
| `vault_append.py` | `vault.autoria.append` |
| `vault_arquitectura_en.py` | `vault.ciclo_de_vida.arquitectura_en` |
| `vault_audit_catalog.py` | `vault.kernel.normativa.audit_catalog` |
| `vault_baseline.py` | `vault.kernel.baseline` |
| `vault_contrato_nota.py` | `vault.kernel.normativa.contrato_nota` |
| `vault_entorno.py` | `vault.kernel.entorno` |
| `vault_env_matrix.py` | `vault.grafo.env_matrix` |
| `vault_errors_trace.py` | `vault.kernel.errors_trace` |
| `vault_escaneo_grafo.py` | `vault.kernel.escaneo_grafo` |
| `vault_firma_sitio.py` | `vault.meta_toolkit.estandar.firma_sitio` |
| `vault_fix_brackets.py` | `vault.autoria.fix_brackets` |
| `vault_frontmatter_completar.py` | `vault.autoria.frontmatter_completar` |
| `vault_frontmatter_heal.py` | `vault.autoria.frontmatter_heal` |
| `vault_fs.py` | `vault.kernel.fs` |
| `vault_fuente_unica.py` | `vault.gobernanza.fuente_unica` |
| `vault_fundamentals_catalog.py` | `vault.kernel.normativa.fundamentals_catalog` |
| `vault_graph_fix.py` | `vault.grafo.graph_fix` |
| `vault_graph_inspect.py` | `vault.grafo.graph_inspect` |
| `vault_history_compact.py` | `vault.ciclo_de_vida.history_compact` |
| `vault_index.py` | `vault.indices.indice` |
| `vault_link_safety.py` | `vault.grafo.link_safety` |
| `vault_list.py` | `vault.autoria.listar` |
| `vault_log_error.py` | `vault.autoria.log_error` |
| `vault_mcp.py` | `vault.meta_toolkit.mcp` |
| `vault_merge.py` | `vault.autoria.merge` |
| `vault_mermaid_reglas.py` | `vault.kernel.normativa.mermaid_reglas` |
| `vault_norms_catalog.py` | `vault.kernel.normativa.norms_catalog` |
| `vault_project_status.py` | `vault.autoria.project_status` |
| `vault_raiz.py` | `vault.kernel.raiz` |
| `vault_registry.py` | `vault.kernel.registry` |
| `vault_runbook_log.py` | `vault.autoria.runbook_log` |
| `vault_sanacion.py` | `vault.ciclo_de_vida.sanacion` |
| `vault_secret_scan.py` | `vault.gobernanza.secret_scan` |
| `vault_section.py` | `vault.indices.registro_de_secciones` |
| `vault_security_rules.py` | `vault.gobernanza.security_rules` |
| `vault_spec_catalog_check.py` | `vault.meta_toolkit.estandar.spec_catalog_check` |
| `vault_spec_generate_catalog.py` | `vault.meta_toolkit.spec_generate_catalog` |
| `vault_subgraph.py` | `vault.consulta.subgraph` |
| `vault_supersede.py` | `vault.autoria.supersede` |
| `vault_test_runner.py` | `vault.meta_toolkit.test_runner` |
| `vault_test_scope.py` | `vault.meta_toolkit.estandar.test_scope` |
| `vault_token_counter.py` | `vault.consulta.token_counter` |
| `vault_vcs.py` | `vault.kernel.vcs` |
| `vault_version.py` | `vault.kernel.version` |
| `vault_vocabulario.py` | `vault.kernel.normativa.vocabulario` |

## 4. Los contextos, medidos

- **10** contextos, **20** fronteras permitidas.
- **179** módulos declarados en los contextos.

| Contexto | Módulos |
|---|---:|
| autoria | 47 |
| ciclo_de_vida | 10 |
| cli | 8 |
| consulta | 11 |
| durabilidad | 4 |
| gobernanza | 13 |
| grafo | 15 |
| indices | 7 |
| kernel | 24 |
| meta_toolkit | 40 |

## 5. Las generaciones de refactor, y qué de cada una sigue vivo

### v40.0–v40.3 · contextos (`f0ab0fc`)

Nace la estructura de contextos y el puente ADR-0002 (las fachadas `sys.modules[__name__] = _dueno`).

- Tocó **224** ficheros; **siguen 223**.
- Dónde: scripts 110, tests 66, vault 32, docs 6, mcp 3, cli 2, README.md 1, pyproject.toml 1, vault-obsidian-architecture.md 1, vault-sandbox 1.

### v40.20–v40.27 · núcleo y dueños (`d899e73`)

Nacen los catálogos: los dueños de los criterios. No toca el corazón.

- Tocó **30** ficheros; **siguen 29**.
- Dónde: scripts 13, docs 7, cli 2, tests 2, README.md 1, mcp 1, pyproject.toml 1, vault-obsidian-architecture.md 1, vault-sandbox 1.

### v41.25–v41.26 · reestructura/teseo (la actual) (`dd86ee3`)

El ejecutor en proceso, los bancos en paralelo, la frontera de producto (`vault_toolkit/`) y los inventarios C-01/C-04/C-06.

- Tocó **231** ficheros; **siguen 229**.
- Dónde: audits 61, scripts 45, vault 44, tests 43, normas 10, docs 9, .github 2, cli 2, empaquetado 2, mcp 2, schemas 2, .gitignore 1, AGENTS.md 1, README.md 1, pyproject.toml 1, vault-obsidian-architecture.md 1, vault-sandbox 1, vault_toolkit 1.

### La actual, según su propio registro

- `audits/reestructura/CHANGELOG-REFACTOR.md`: **53** commits registrados.
- Fases: A-1, A-2, A-3, A-5, B-04, B-1, B-2, B-3, C-06, C-1, C-2, S-4.
- Su predecesora está archivada y medida en `audits/archivo/reestructura-2026-11-02/`.

