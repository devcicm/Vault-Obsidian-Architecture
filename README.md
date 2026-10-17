# Vault Obsidian Architecture

Vault Obsidian Architecture es un estándar abierto con un toolkit para dar a agentes LLM memoria documental persistente, auditable y gobernada sobre Markdown plano.

[![Version](https://img.shields.io/badge/version-v41.7-blue)](./vault-obsidian-architecture.md)
[![Tools](https://img.shields.io/badge/tools-124_active-green)](./scripts/)
[![Scripts](https://img.shields.io/badge/scripts-162_total-lightblue)](./scripts/)
[![Python](https://img.shields.io/badge/python-3.9+-yellow)](./scripts/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

---

## Qué es

Este repositorio reúne el estándar que define cómo construir la memoria
documental y las herramientas que lo implementan. El vault de cada proyecto
es una instancia de esa memoria; aquí, `vault-sandbox/` es el vault de pruebas.

## El problema

Entre sesiones, un agente puede perder el contexto del trabajo anterior:
errores ya resueltos, estado del proyecto, decisiones técnicas, infraestructura
y reglas de negocio. Volver a explicarlo cuesta tiempo y dificulta seguir
el origen de una decisión.

El estándar propone conservar ese conocimiento en documentos que el agente
pueda consultar y actualizar, con metadatos, relaciones y trazabilidad.

## Para quién sirve

Para desarrolladores e integradores que usan agentes en proyectos con trabajo
acumulado entre sesiones, y para maintainers que necesitan revisar cómo se
conserva y evoluciona ese conocimiento.

El agente necesita acceso al vault mediante su entorno de ejecución o
herramientas. Obsidian es una interfaz humana compatible; no es necesario
tenerlo instalado para que el agente utilice la memoria.

## Estándar, toolkit y runtime

| Nivel | Qué aporta |
|---|---|
| **Estándar** | Define estructura, reglas, contratos y gobernanza de la memoria documental. |
| **Toolkit** | Implementa captura, consulta, custodia, recuperación y verificaciones del estándar. Incluye `scripts/`, el paquete `vault/` y las interfaces `cli/` y `mcp/`. |
| **Runtime** | Es el vault concreto de un proyecto: su memoria operativa, notas, relaciones, preferencias, índices y artefactos. |

Esta distinción explica el producto. Las capacidades y naturalezas del servicio
siguen definidas en [su registro canónico](./scripts/vault_servicio.py).

## Cómo fluye el conocimiento

Evidencia → captura → conocimiento gobernado → persistencia → recuperación
→ selección contextual → siguiente sesión del agente.

El agente registra hechos, decisiones y aprendizajes. Las herramientas aplican
las reglas que cubren, mantienen artefactos y permiten recuperar una selección
como contexto. El agente o su harness —el entorno que ejecuta sus herramientas
y prepara su contexto— debe incorporar este recorrido a su trabajo.

## Límites y garantías reales

La memoria se conserva en archivos locales, sin base de datos, embeddings ni
servicio externo obligatorio. Las notas son Markdown con frontmatter YAML y
wikilinks, legibles por una persona aunque deje de usar el toolkit.

Las herramientas ofrecen validaciones, trazabilidad y mecanismos de recuperación
según sus contratos. Una puntuación de salud no demuestra por sí sola que todo
el contenido sea verdadero, completo o relevante. Las ediciones externas al
toolkit no pasan automáticamente por sus guards, y conservar documentos no
hace que un agente los consulte u obedezca por sí mismo.

El alcance de las normas está en el [catálogo](./vault/kernel/norms_catalog.py);
la evidencia de soporte y sus huecos, en la
[guía de producción](./docs/GUIA-DE-PRODUCCION.md).

---

## Estado del proyecto — léelo antes de instalar

**Funciona y se usa a diario, lo mantiene una persona, y evoluciona rápido.** Eso
último no es un adorno: significa que hay cosas que todavía no están probadas
donde importa, y prefiero decirlas aquí que dejar que las descubras tú.

- **Se instala con `pip install -e .`** Entry points: `vault` y `vault_gobernanza`.
  El servidor MCP no tiene dependencias npm — solo Node 18+ built-ins.
- **VAULT_ROOT es la única variable esencial.** Sin ella, las tools auto-detectan
  buscando `vault-*/` en el directorio actual; si la detección cae en el propio
  paquete instalado, se niegan con `VAULT_NOT_FOUND` en vez de leerlo como vault
  (posterior a 41.6, ver `docs/INSTALACION-LIMPIA.md`).
- **El servidor MCP por HTTP (`--port`) escucha en `127.0.0.1` y exige token**
  (`Authorization: Bearer`, desde `VAULT_MCP_TOKEN` o generado e impreso por
  stderr al arrancar). Rechaza peticiones de navegador (`Origin`) y un `Host`
  distinto de `127.0.0.1`/`localhost`. No es autenticación de red: ponerlo detrás
  de un proxy inverso sigue sin ser un uso soportado. Por stdio no hay puerto.
- **Contra un vault que no sea tuyo, primero solo lectura:**
  `python scripts/vault_foreign_check.py --root <ruta>`.

Los huecos conocidos no están escondidos: están **medidos** y publicados en
[`docs/GUIA-DE-PRODUCCION.md`](./docs/GUIA-DE-PRODUCCION.md), que se genera desde
un registro ejecutable — si un hueco se cierra, la guía cambia sola; si alguien
lo declara cerrado sin cerrarlo, falla una puerta.

### Los issues están abiertos, y los de fuera son los que más valen

Incluido el que solo dice «lo intenté y me perdí en el minuto dos». La razón es
concreta: **todas las puertas de calidad de este repo miden el repo contra sí
mismo**, y en esa sala no está el consumidor. La primera vez que se preguntó en
serio «¿puede usar esto otra persona?» apareció en diez minutos un defecto que
ninguna puerta veía — el paquete prometía Python 3.9 y ninguna máquina ejecutaba
3.9. Tú ves lo que el proyecto no puede verse.

Cómo reportar y enviar PR: abrir un issue o pull request en el repo.
Fallos de **seguridad** en privado, nunca en un issue: [SECURITY.md](SECURITY.md) dice por dónde.

---

## Qué leer después

| Si necesitas… | Sigue con… |
|---|---|
| Entender el propósito, las promesas y los límites | [Visión de producto](./docs/product/overview.md) |
| Situar las piezas y sus responsabilidades | [Seis capas conceptuales](./docs/architecture/layers.md) |
| Poblar memoria desde un proyecto sin vault | [Onboarding](./docs/MODO-AGENTICO-ONBOARDING.md) |
| Adaptar un vault preexistente | [Sanación](./docs/MODO-AGENTICO-SANACION.md) |
| Consultar la instalación y el uso documentados | [Quick Start](#quick-start), con su limitación de copia indicada |
| Quitar una instalación previa, instalar la wheel y registrar el MCP | [Instalación limpia](./docs/INSTALACION-LIMPIA.md) |
| Ver auditorías, comparativas entre versiones y documentos archivados | [Índice de `docs/`](./docs/README.md) |
| Elegir y ejecutar herramientas | [Referencia de scripts](./scripts/README.md) y [CLI consolidada](./cli/README.md) |
| Consultar la norma y la arquitectura vigente | [Manifiesto](./vault-obsidian-architecture.md), [arquitectura](./docs/ARQUITECTURA.md) y [blueprint](./docs/BLUEPRINT.md) |

---

## Quick Start

### 1. Clonar e instalar

```bash
git clone https://github.com/devcicm/Vault-Obsidian-Architecture.git
cd Vault-Obsidian-Architecture
```

**CLI + entry points** (Python 3.9+, pip):

```bash
pip install -e .
```

**MCP server** (Node 18+):

```bash
# Instalado con pip (wheel o `pip install .`): el servidor viaja en el paquete.
# Imprime su ruta y la entrada lista para la configuración del cliente MCP,
# con VAULT_MCP_PYTHON fijado al intérprete del venv. Pon tu VAULT_ROOT.
vault mcp-path

# Alternativa desde el checkout — Opción A: symlink (requiere sudo en Linux/macOS)
sudo ln -sf "$(pwd)/mcp/nodejs/vault-mcp-server.mjs" /usr/local/bin/vault-mcp

# Opción B: python installer
python -m vault.install --mcp
```

Para un agente, añade `VAULT_MCP_PERFIL=agente` al `env` de la entrada MCP: el
servidor ofrece y acepta solo las tools del protocolo de sesión —orientarse,
recordar, escribir, borrar y cerrar—, derivadas de
`vault.meta_toolkit.protocolo_de_sesion`. Sin ella expone el catálogo entero.

**Desinstalar:**

```bash
pip uninstall -y vault-obsidian-architecture
# Si instalaste MCP:
rm -f /usr/local/bin/vault-mcp
# O con el uninstaller:
python -m vault.uninstall --mcp
```

### 2. Variables de entorno

La única variable esencial es `VAULT_ROOT`:

```bash
export VAULT_ROOT=/ruta/al/tu-vault
```

Sin ella, las tools auto-detectan el vault buscando `vault-*/` en el directorio actual.
Para que una detección dudosa falle en vez de adivinar, exporta también
`VAULT_STRICT_ROOT=1`.

Toda escritura lleva autor. `vault_write` y las tools que escriben notas lo leen de
`--meta '{"agent":"<nombre>"}'` o, si no viene, de `VAULT_AGENT`; sin ninguno de los dos
la escritura se rechaza con su `recovery`, no se firma como anónima:

```bash
export VAULT_AGENT=claude
```

### 3. Inicializar un vault nuevo

```bash
# Bootstrap completo: carpetas, versión, hub, índices navegables y nota de comandos
vault init vault-mi-proyecto
export VAULT_ROOT="$PWD/vault-mi-proyecto"

vault tools list                        # ver las tools disponibles
```

`vault init` sobre un vault que ya existe no lo repuebla: responde
`INIT_ALREADY_INITIALIZED`.

### 4. `.gitignore` para el consumer repo

```gitignore
.claude/
vault-*/scripts/
vault-backups/
vault_obsidian_architecture.egg-info/
```

### 5. Verificar la instalación

```bash
vault --version                          # CLI version
vault tools list                         # tools activas
python -m vault.gobernanza.tool --help   # tool de gobernanza
vault-mcp --help                         # MCP server (si instalado)
```

### 6. Documentar el proyecto

```bash
# Identidad del vault
python scripts/vault_write.py --folder "00_System" \
  --title "Vault Identity" \
  --meta '{"cia_integrity":"high","agent":"claude","type":"identity"}' \
  --content "Vault del proyecto X. Agente: claude."

# Registrar el proyecto: las tools de proyecto lo exigen (PROJECT_NOT_FOUND si falta)
python scripts/vault_project.py --add mi-proyecto --title "Mi proyecto"

# Overview del proyecto
python scripts/vault_project_overview.py \
  --project "mi-proyecto" \
  --description "Descripción del proyecto" \
  --runtime "Node.js 20"

# Documentar un módulo (IEEE 1016) e inyectar @vault: en el archivo fuente
python scripts/vault_code_module.py \
  --project "mi-proyecto" \
  --file_path "src/services/AuthService.ts" \
  --description "Servicio de autenticación JWT" \
  --language typescript \
  --iso_type service \
  --tag-source

# Auditar trazabilidad bidireccional código ↔ vault
python scripts/vault_code_sync.py --project "mi-proyecto" --report
python scripts/vault_code_sync.py --project "mi-proyecto" --fix   # inyecta @vault: donde falte

# Auditar el vault
python scripts/vault_audit.py
```

---

## CLI consolidada — `vault`

Las 124 tools bajo un único punto de entrada, con búsqueda, planificación de
concurrencia y guardas de seguridad:

```bash
vault --version                         # versión
vault tools list                         # todas las tools
vault tools show vault_gobernanza       # detalle de una tool
vault run vault_audit                   # ejecutar una tool
```

El entry point `vault` se instala con `pip install -e .`. Guía:
[`cli/README.md`](cli/README.md) · Referencia de comandos:
[`cli/COMMANDS.md`](cli/COMMANDS.md).

---

## Qué es un vault

```
vault-{nombre}/          ← carpeta raíz (prefijo vault- obligatorio)
├── 00_System/           — identidad, reglas, contratos del agente
├── 01_Projects/         — overview, envs, estado por proyecto
├── 02_Observability/    — errores, vulnerabilidades, métricas, SLOs, maintenance/
├── 03_Decisions/        — ADRs y decisiones técnicas
├── 04_Sessions/         — bitácoras de sesión del agente
├── 05_Patterns/         — patrones con ciclo de vida evolutivo
├── 06_Diagrams/         — ERDs y diagramas Mermaid auto-generados
├── 07_Knowledge/        — glosario, APIs, conceptos, reglas de negocio
├── 08_Runbooks/         — procedimientos operacionales paso a paso
├── 09_Infrastructure/   — servidores, servicios, redes, pipelines CI/CD
├── 10_Migrated/         — documentación externa en tránsito
├── 11_Code/             — documentación de código IEEE 1016 por módulo
├── 12_Bibliography/     — fuentes externas consultadas por el agente
├── 13_Flows/            — flujos de trabajo, pipelines, ciclos de vida
├── 14_Requirements/     — requerimientos ISO 29148
├── 15_Tests/            — casos de test ISO 29119
├── 16_AI_Governance/    — decisiones de agentes IA (ISO 42001)
├── 17_Preferences/      — contexto estable del usuario (workflow, style, tooling…)
├── 18_Bugs/             — defectos con ciclo propio: open → root-causes → fixed
├── 19_Audits/           — bitácora del vault: auditorías y vocabulario introducido
├── 20_Quarantine/       — notas retenidas sin destino seguro (nunca borradas)
├── 21_QA/               — planes de test, métricas, reportes (ISO 9001, ISO 25010)
└── 99_Index/            — search-index.json, graph.json
```

Formato: **Markdown + YAML frontmatter + wiki-links**. Compatible con git, abre en cualquier editor, renderable en Obsidian Desktop.

---

## Garantías de datos

Un vault no es una carpeta de notas: es un activo de datos con garantías medibles.
Cada una tiene una métrica, una tool que la calcula y un artefacto donde queda escrita.
Detalle completo en [Marco de Datos y Gobernanza](./vault-obsidian-architecture.md#marco-de-datos-y-gobernanza).

| Eje | Qué garantiza | Dónde se mide |
|---|---|---|
| **Tríada CIA** (pilar) | Confidencialidad, Integridad, Disponibilidad como campos de frontmatter que **cambian el comportamiento de las tools**, no como etiquetas | `cia_sensitivity` / `cia_integrity` / `cia_availability` |
| **8 Fundamentos (F1–F8)** | Integridad, consistencia, completitud, exactitud, validez, actualidad, autenticidad, no-repudio | `vault_fundamentals`, `00_System/data-fundamentals.json` |
| **9 dimensiones DQ** | Los 8 fundamentos + unicidad, escala 0.0–1.0, umbral 0.7 | `vault_quality_check`, `00_System/quality-index.json` |
| **Principios FAIR** | Findable, Accessible, Interoperable, Reusable — con el mecanismo concreto que ya los cumple | `vault_search`, `vault_master_index`, `.history/` |
| **V's del Big Data** | Volumen, velocidad, variedad, veracidad, valor, variabilidad — cada V apunta a un número real | `vault_audit`, `vault_change_log`, `vault_delta` |
| **Trazabilidad** | Cadena verificable `agent:` → `.change-log.json` → `.tool-trace.json` → `.history/` → manifiesto Merkle | `vault_audit --trace` |
| **Gobernanza** | 80 normas AP/PAT/SP/CN, 0 con enforcement manual | `vault_norms --audit` |
| **Alineación ISO** | 13 normas mapeadas cláusula → implementación → tool | `vault_fundamentals --framework` |

```bash
python scripts/vault_fundamentals.py --framework   # exporta el marco completo (JSON + MD)
python scripts/vault_fundamentals.py --matrix      # matriz concepto → métrica → tool → enforcement
python scripts/vault_norms.py --check-framework    # guard anti-drift registro ↔ manifiesto
```

---

## Novedades v40.35 — Producto para terceros

- **El MCP por HTTP ya no está abierto.** Exige `Authorization: Bearer` (`VAULT_MCP_TOKEN`
  o el token que el servidor imprime al arrancar) y rechaza `Origin` y `Host` ajenos
  (SP-04). Los argumentos se validan contra el schema antes de ejecutar nada.
- **Nada sale del vault.** `vault_diff` no compara ficheros de fuera, los envelopes de
  error no publican rutas absolutas ni traceback (salvo `VAULT_DEBUG=1`) y con un
  `VAULT_ROOT` que no existe ninguna tool se ejecuta, y el rechazo dice qué corregir.
- **Identidad sin ambigüedad.** Registro de proyectos (`vault_project`, AP-63), nombres
  de fichero con `slugify_strict` (CN-01), `Status` y `ErrorCode` derivados de sus
  registros y la nota abre con su título como H1 (CN-04).
- **Escrituras íntegras.** Un solo escritor de frontmatter (AP-46) y locks que excluyen
  de verdad entre procesos (F1).
- **Wheel de producto.** Deja fuera la gobernanza del estándar y lleva dentro el servidor
  MCP, así que funciona sin un checkout del repo.

## Novedades v40.34 — Toolkit instalable + Gobernanza MCP

- **`pip install -e .` validado end-to-end.** La receta de instalación por copia de carpetas
  queda sustituida por el entry point oficial: `pip install -e .` instala `vault` y
  `vault_gobernanza` como comandos de shell. El paseo completo (clone → pip → uso) está
  probado y documentado.
- **`vault_gobernanza` como tool de primera clase.** Integrada en el catálogo MCP
  (`script=None`, `execution_module="vault.gobernanza.tool"`), expuesta via
  `__module__:` prefix en el servidor MCP, con entry point propio en `pyproject.toml`.
  El guard chain de gobernanza del MCP ahora es invocable desde CLI: `vault_gobernanza
  --content "..." --vault-root /ruta`.
- **MCP server zero-dependencies.** El servidor en `mcp/nodejs/vault-mcp-server.mjs`
  sigue sin ninguna dependencia npm — solo Node.js built-ins. Soporta `--mcp` install
  via symlink a `/usr/local/bin/vault-mcp`.
- **Instaladores y desinstaladores** en `vault/install.py`, `vault/uninstall.py`,
  `install.sh`, `uninstall.sh`, `install-mcp.sh`, `uninstall-mcp.sh`. Cobertura:
  CLI (+ entry points), MCP server, desinstalación completa.
- **23 gates verdes en 22 puertas.** `vault_gate --strict` pasa completo; la puerta de
  `vault_blueprint` se regenera automáticamente. 3198 tests en la suite.

## Novedades v40.33 — Adapter de modelo LLM

- **El vault se adapta al modelo que lo consume, sin configuración.** El budget de contexto
  de `vault_context_pack` era un número fijo (4000 tokens) independiente de la ventana real
  del modelo. Ahora `vault_model_profile` auto-detecta el modelo desde `clientInfo.name`
  del handshake MCP, lo resuelve contra `17_Preferences/model_profiles.json` y expone el
  budget correcto.
- **Tres capas, una sola decisión:** el servidor MCP detecta y propaga `VAULT_MODEL_PROFILE`,
  la tool la lee a través del registro de entorno (`leer()`), y `vault_context_pack` la
  consume al resolver el budget — claude/cursor 15000, gpt-4o 8000, deepseek 6000, gemini 4000,
  cualquier modelo nuevo 2000 (floor).
- **`vault_fix_all.py`** — un comando que regenera todos los artefactos derivados del registro
  en el orden correcto (`tools-catalog`, `env-table`, baselines de campos, blueprints, cifras).
  Cierra el drift recurrente de documentación derivada.

## Novedades v39.0 — Marco de Datos y Gobernanza explícito

- **Sección nueva en el manifiesto**: CIA, F1–F8, 9 dimensiones DQ, FAIR, V's del Big Data,
  estados, versionado en tres planos, trazabilidad, gobernanza, cobertura ISO y matriz de
  trazabilidad de 20 filas — todo con métrica, umbral, tool y artefacto.
- **Registro canónico ejecutable** en `scripts/vault_fundamentals.py` (`CIA_TRIAD`,
  `FAIR_PRINCIPLES`, `BIGDATA_VS`, `ISO_COVERAGE`, `TRACEABILITY_MATRIX`).
- **Guard anti-drift**: `vault_norms.py --check-framework` falla si el manifiesto omite
  cualquier id del registro. La doc ya no puede desincronizarse del código en silencio.
- **Política de no-derogación** declarada: nada se elimina; lo reemplazado se anota
  `superseded_by:` conservando su contrato.
- **Changelog consolidado**: entradas faltantes reconstruidas desde git, orden cronológico
  restaurado y hashes `pending` fijados.
- **AP-38 — vocabulario cerrado normalizado al escribir** (`guard+audit`): un censo de
  **17 vaults reales, 2.929 notas**, encontró **54 valores de `status` con solo el 6%
  canónico**, pese a que CN-03 lo audita desde v38. La causa no eran los agentes: el
  toolkit publicaba **nueve** vocabularios de `status` en competencia y auditaba contra
  uno. `normalize_status()` corrige en `vault_write`, `DOMAIN_STATUS_VOCABS` separa el eje
  de dominio (`test_result`, `bug_state`…) del ciclo de vida. Cobertura: 608 de 609 notas.
- **AP-39 — vocabulario abierto con memoria** (`guard+audit`): 1.180 tags para 6.358 usos,
  **45% usados una sola vez** y una tasa de invención **plana durante tres meses**. Los
  tags se resuelven contra el registro antes de escribir y el término nuevo se admite pero
  **queda anotado** en la bitácora append-only `19_Audits/vocabulary/tag-ledger.json` con
  quién, cuándo y en qué nota. Heal: `vault_tags --backfill-ledger`.
- **AP-40 — contrato publicado que la CLI rechaza** (`guard+audit`): **45 de 82 tools**
  publicaban en el catálogo MCP parámetros que su propio `argparse` no acepta, y como el
  servidor compone `--<param>` literal, más de la mitad de la superficie MCP fallaba en cada
  invocación. Había un guard de sincronía en verde: comparaba el JSON contra el Python del
  que se genera, y **dos copias de la misma equivocación coinciden**. Ahora el contrato se
  deriva del script por AST. Audit: `vault_mcp_catalog --check-params`.
- **AP-41 — máquina de estados declarada sin verificar** (`guard+audit`):
  `STATUS_TRANSITIONS` existía desde v38 y su único consumidor era su propio test, así que
  una nota `archived` podía volver a `draft`. El camino de lectura que hacía falta para
  comprobarlo estaba **en la rama del `else`**, la del caso en que la nota no existe: cada
  actualización acuñaba un `id` nuevo, reseteaba `createdAt` y degradaba el estado a
  `draft`. Guard en `vault_write`, audit sobre `.history/`, sin heal — el estado actual es
  un hecho y el camino irregular es la información.
- **AP-42 — tool publicada sin haberse ejecutado nunca** (`guard+audit`): `--help` demuestra
  que el `argparse` se construye, nada más. El primer barrido real —el ejemplo documentado
  de cada tool, contra una copia desechable del sandbox— dio **41 de 87 fallando**, y 36 lo
  hacían porque el `example` del catálogo usaba flags que la propia CLI rechaza: AP-40
  trasladado a la documentación, con el usuario copiando del README algo que no corre.
  Corregidas las 41, la baseline nació en **0**: guard duro desde el primer día.
  Gate: `vault_smoke --check --strict`.
- **AP-43 — norma sin refuerzo en el punto de uso** (`guard+audit`): el catálogo de normas
  estaba completo y era invisible — el agente se enteraba de que una norma existe al
  incumplirla, y solo si era una de las 14 que previenen en vez de una de las 33 que solo
  detectan. Ahora **el vault le habla al agente en cada interacción**: `wrap_main` añade a
  cada resultado un bloque `vault_says` con la norma que acaba de actuar, cuántas notas
  cambiaron y qué mirar después, rotando el foco para que el refuerzo no se vuelva ruido.
  Vive en el único punto por el que ya pasa la salida de todas las tools, porque una capa
  que hubiera que invocar tool por tool sería el registro-que-nadie-consume de siempre.
  Consulta: `vault_voice --tool <tool>` / `--coverage`.
- **Grupo 36 y tres secciones nuevas**, derivadas de medir y no de diseñar: `18_Bugs/`
  (`vault_bug_save` — el defecto tiene ciclo propio: síntoma → causa raíz → corrección
  verificada), `19_Audits/` (la bitácora del vault) y `20_Quarantine/` (`vault_quarantine`
  — retener sin borrar, porque la alternativa a retener no es limpiar, es `rm`).

---

## Novedades v38.1 — Contención, idempotencia y enforcement total

- **AP-36** (critical): toda operación escribe solo dentro del vault, es idempotente
  y deja artefactos rastreables. Backups en `VAULT_ROOT/vault-backups/`, `.bak` de
  moves en `00_System/.trash/`, stubs de mantenimiento en `02_Observability/maintenance/stubs/`.
- **0 normas con enforcement `manual`**: las 80 normas del catálogo tienen guard o audit.
  `python scripts/vault_norms.py --audit [--root X]` audita AP-06/07/09/10/15/19/36, CN-02/03, SP-01.
- **Saneamiento de índices**: tablas con `| [[stem]] | Título | ... |` (nunca alias en
  celda); `python scripts/vault_section_index.py --heal` cura índices legacy; escribir
  un `index.md` a mano dispara la regeneración canónica automática.
- **`STATUS_VOCAB` unificado** (12 valores) como fuente única del vocabulario de `status`.
- **Vault-root lazy**: `set_vault_root()/get_vault_root()` — traces/locks/índices siguen
  al `--root` objetivo.

---

## Las 124 tools activas — 37 grupos

| Grupo | Tools |
|---|---|
| 1 — Core | `vault_write`, `vault_read`, `vault_search`, `vault_list`, `vault_append`, `vault_diff`, `vault_merge`, `vault_move` |
| 2 — Observabilidad | `vault_log_error` |
| 3 — Patrones | `vault_pattern_save`, `vault_pattern_list` |
| 4 — Diagramas | `vault_diagram_save`, `vault_diagram_export`, `vault_mermaid_check`, `vault_relation_add` |
| 5 — Conocimiento | `vault_knowledge_save`, `vault_knowledge_get` |
| 6 — Salud del Vault | `vault_audit`, `vault_validate`, `vault_graph`, `vault_graph_merge`, `vault_graph_inspect`, `vault_fuente_unica` |
| 7 — Runbooks | `vault_runbook_save`, `vault_runbook_log` |
| 8 — Infraestructura | `vault_infra_save`, `vault_infra_map`, `vault_env_save`, `vault_env_matrix` |
| 9 — Migración | `vault_migrate_docs`, `vault_migrate_rollback` |
| 10 — Línea de tiempo | `vault_timeline` |
| 11 — Vista del proyecto | `vault_project_status`, `vault_project_overview` |
| 12 — Código | `vault_code_module`, `vault_code_relation`, `vault_code_map`, `vault_code_query`, `vault_code_sync` |
| 13 — Backups | `vault_backup`, `vault_backup_list`, `vault_backup_base64`, `vault_restore`, `vault_restore_base64` |
| 14 — Seguridad | `vault_security_scan` |
| 15 — Índices | `vault_section_index`, `vault_master_index`, `vault_reindex` |
| 16 — Bibliografía | `vault_bibliography_save` |
| 17 — Drift Detection | `vault_drift_detect` |
| 18 — Flujos | `vault_flow_save` |
| 19 — Requerimientos | `vault_requirement_save` |
| 20 — Tests | `vault_test_save` |
| 21 — IA Governance | `vault_ai_decision` |
| 22 — Versionado | `vault_standard_upgrade` |
| 23 — Change Log | `vault_change_log` |
| 24 — Data Quality | `vault_quality_check`, `vault_fundamentals` |
| 25 — Propagación | `vault_impact`, `vault_propagate` |
| 26 — Tokens | `vault_tokens`, `vault_token_counter`, `vault_token_service` |
| 27 — Session Delta y Tags | `vault_delta`, `vault_tags` |
| 28 — Producción y SRE | `vault_incident_save`, `vault_slo_save` |
| 29 — Release | `vault_release_save` |
| 30 — Riesgos y Calidad | `vault_risk_save`, `vault_privacy_save`, `vault_ncr_save` |
| 31 — Bootstrap | `vault_init`, `vault_onboard` |
| 32 — Gestión de Carpetas | `vault_folder_registry`, `vault_section` |
| 33 — Corrección automática | `vault_fix_brackets`, `vault_frontmatter_heal`, `vault_graph_fix` |
| 34 — Memoria de Contexto | `vault_preferences`, `vault_query_parse`, `vault_subgraph`, `vault_context_pack`, `vault_ingest`, `vault_model_profile` |
| 35 — Normas | `vault_norms`, `vault_arch`, `vault_gate`, `vault_smoke`, `vault_servicio`, `vault_blueprint`, `vault_doc_counts`, `vault_doc_sync`, `vault_blame_audit`, `vault_changelog_check`, `vault_error_contract`, `vault_noop_audit`, `vault_voice`, `vault_norms_coherence`, `vault_criterios`, `vault_ciclos`, `vault_kernel`, `vault_excepcion_declarada`, `vault_recursos`, `vault_produccion`, `vault_foreign_check`, `vault_code_tag` |
| 36 — Defectos y Cuarentena | `vault_bug_save`, `vault_quarantine` |
| 37 — Skills | `vault_sdd_init`, `vault_sanacion` |

Ver **[scripts/README.md](./scripts/README.md)** para contratos completos con parámetros, ejemplos y protocolo de sesión.

---

## Protocolo de sesión (resumen)

```bash
# Inicio de sesión
python scripts/vault_standard_upgrade.py --check        # verificar versión
python scripts/vault_reindex.py                         # actualizar índice + hash-index
python scripts/vault_audit.py                           # baseline de salud + tagHealth
python scripts/vault_delta.py --snapshot                # guardar baseline de hashes
python scripts/vault_drift_detect.py --path "." --project {slug} --mode snapshot

# Cierre de sesión
python scripts/vault_delta.py                           # qué cambió, qué está stale
python scripts/vault_drift_detect.py --path "." --project {slug} --mode report
python scripts/vault_tags.py                            # actualizar tag registry
python scripts/vault_reindex.py --graph
python scripts/vault_audit.py                           # healthScore ≥ baseline
python scripts/vault_spec_memory.py --check             # actualizar spec-memory
```

---

## CIA schema + Data Quality (v27–v28)

Cada nota generada incluye clasificación de seguridad y calidad:

```yaml
cia_integrity:    high        # critical | high | medium | low
cia_availability: medium      # high | medium | low
cia_sensitivity:  internal    # public | internal | restricted
agent:            claude      # quién generó la nota (F7 AUTENTICIDAD)
```

`vault_quality_check` evalúa 9 dimensiones por nota (integridad, consistencia, completitud, exactitud, validez, actualidad, autenticidad, no-repudio, unicidad) y genera `00_System/quality-index.json`.

### 8 Fundamentos de Datos (F1–F8)

Cada tool está mapeada a uno o más fundamentos. `vault_fundamentals` es el registro canónico.

| ID | Principio | Tools clave |
|---|---|---|
| F1 | INTEGRIDAD | `vault_write`, `vault_validate`, `vault_quality_check` |
| F2 | CONSISTENCIA | `vault_audit`, `vault_graph`, `vault_impact`, `vault_propagate` |
| F3 | COMPLETITUD | `vault_write`, `vault_append`, `vault_knowledge_save` |
| F4 | EXACTITUD | `vault_drift_detect`, `vault_diff` |
| F5 | VALIDEZ | `vault_validate`, `vault_security_scan` |
| F6 | ACTUALIDAD | `vault_audit`, `vault_drift_detect`, `vault_backup` |
| F7 | AUTENTICIDAD | `vault_write`, `vault_ai_decision`, `vault_bibliography_save` |
| F8 | NO_REPUDIO | `vault_change_log`, `vault_log_error`, `vault_timeline` |

---

## Seguridad (v28)

Todas las tools de escritura incluyen tres capas de protección:

| Capa | Mecanismo | Qué previene |
|---|---|---|
| Path validation | `assert_within_vault()` en `vault_io.py` | Path traversal absoluto (`/etc/passwd`) y relativo (`../../`) |
| Atomic writes | `atomic_write_text` / `atomic_write_json` | Escrituras parciales por kill del proceso |
| CIA frontmatter | Campos obligatorios en los 12 scripts de escritura | Notas sin clasificación de seguridad |

---

## Implementaciones de referencia

### vault-electron-fingerprint

Sistema de control de asistencia con autenticación biométrica.

- **Stack:** ElectronJS 31 + TypeScript + better-sqlite3 + motor .NET C# (sensor DP4500)
- **Vault:** 13 notas — arquitectura, ERD, 2 flujos biométricos, BiometricService (IEEE 1016), API engine, schema SQLite, infra map, envs
- **Health score al cierre:** 100/100 · 0 huérfanas · 0 links rotos · 21 entradas en search index
- **Repo:** [ElectronJS---Autenticacion-por-huella-dactilar](https://github.com/devcicm/ElectronJS---Autenticacion-por-huella-dactilar) · rama `sistema-asistencia` · carpeta `vault-electron-fingerprint/`

---

## La especificación completa

**[vault-obsidian-architecture.md](./vault-obsidian-architecture.md)** — ~11000 líneas.

Contiene:
- 8 principios de diseño
- 124 tools con contratos exactos (parámetros, retorno, error codes, cuándo usar)
- 80 normas: 66 antipatrones (AP-01–AP-66), 6 patrones (PAT-1–PAT-6), 4 SP, 4 CN
- norm_refs auto-embebido en frontmatter + vault_code_tag para etiquetas en código fuente
- 8 Fundamentos de Datos (F1–F8) con trazabilidad a tools
- CIA schema completo con semántica por tipo de nota
- Data Quality framework (9 dimensiones, índice persistente)
- Propagación graph-aware (BFS sobre wiki-links, 3 estrategias)
- **Spec-driven design:** tool-spec.json + vault_spec_validate — contratos formales antes de implementar
- **Trazabilidad bidireccional:** @vault: tag en código fuente + vault_code_sync para auditar gaps código↔vault
- **Grupo 31 — Bootstrap:** `vault_init` para inicializar un vault fresco en 1 comando (22 folders + scaffolds + audit)
- **Grupo 34 — Memoria de Contexto:** eje consulta → contexto. `vault_query_parse`
  (lenguaje natural → consulta estructurada), `vault_subgraph` (K semillas, N saltos),
  `vault_context_pack` (rerank + Top-K bajo presupuesto de tokens), `vault_preferences`
  (contexto estable del usuario), `vault_ingest` (ingesta con pre-vuelo anti-poison) y
  `vault_model_profile` (budget de tokens adaptado al modelo del agente)
- **nextActions prescriptivo:** `vault_audit` ahora devuelve qué hacer para mantener 100/100
- Grupos 28-31: Producción/SRE, Release, Riesgos/Calidad (ISO 20000, 22301, 12207, 31000, 27701, 9001)
- Mapa canónico script→carpeta (tabla authoritative)
- Protocolo de inicialización corregido con comandos exactos
- Protocolo de sesión para LLMs remotos (Claude API, GPT, Gemini, DeepSeek)
- Sistema de versionado con migraciones automáticas (v19 → v40)
- Changelog completo, desde v1
- Compatibilidad con Obsidian Desktop

---

## Scripts — estructura del repositorio

```
scripts/                    ← 162 archivos Python (124 tools del catálogo + 8 archivadas en _archived/ + internas/meta)
├── vault_io.py             — I/O base: _detect_vault_root, assert_within_vault, atomic_write_text/json, file_lock
├── vault_errors.py         — wrap_main (timeout 60s), emit_ok, trace log
├── vault_write.py          — tool principal de escritura (guards AP-20, AP-21, norm_refs auto-embed)
├── vault_audit.py          — health score (CIA-weighted), DQ health, propagation pending, norm_code, nextActions
├── vault_standard_upgrade.py — migraciones v19→v40, --init, --check, --validate
├── vault_init.py           — bootstrap de 1 comando (22 folders + scaffolds + master_index + reindex + audit)
├── vault_code_module.py    — documentación IEEE 1016 para módulos de código (--tag-source inyecta @vault:)
├── vault_code_sync.py      — auditoría bidireccional código↔vault (complete/missing_tag/orphan, --fix)
├── vault_flow_save.py      — flujos con Mermaid embebido
├── vault_infra_save.py     — componentes de infraestructura + mapa de red auto-generado
├── vault_knowledge_save.py — conocimiento estructurado por categoría
├── vault_diagram_save.py   — diagramas Mermaid/ASCII/PlantUML
├── ...                     — el resto de scripts (ver scripts/README.md)
└── README.md               — referencia completa de parámetros y ejemplos
```

**Requisitos:** Python 3.9+ y PyYAML (dependencia obligatoria declarada en [pyproject.toml](./pyproject.toml))

**Timeout automático:** todas las tools ≤ 60s (configurable via `VAULT_TOOL_TIMEOUT`)  
**JSON siempre:** cualquier error devuelve `{"ok": false, "error_code": "...", "recovery": {...}}`

---

## Compatibilidad

| Entorno | Soporte |
|---|---|
| Bash / Linux / macOS | Completo |
| PowerShell 5.1 (Windows) | Completo — args JSON con `<>` requieren Bash o archivo temporal |
| Claude Code (CLI) | Nativo — tools invocables como subprocess |
| Claude API / GPT / Gemini | Mediante harness que expone las tools como function calls |
| Obsidian Desktop | Compatible — Mermaid rendering, wiki-links nativos, Graph view |

---

## Licencia

MIT — ver [LICENSE](./LICENSE)
