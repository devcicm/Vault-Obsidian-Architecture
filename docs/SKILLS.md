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

| Skill | Versión | Definición | Versiones anteriores | Entry point | Descripción |
|---|---|---|---|---|---|
| `vault-sdd-init` | v2.0 | `agent/skills/vault-sdd-init/SKILL.md` | `agent/skills/vault-sdd-init/SKILL-v1.0.md` | `scripts/vault_sdd_init.py` | Inicializa el SDD (Spec-Driven Development documentation) de un vault |
| `vault-sanacion` | v2.0 | `agent/skills/vault-sanacion/SKILL.md` | `agent/skills/vault-sanacion/SKILL-v1.0.md` | `scripts/vault_sanacion.py` | Diagnostica un vault preexistente y devuelve el plan de 12 fases con veredicto y evidencia. **No escribe** |
| `vault-onboard` | v2.0 | `agent/skills/vault-onboard/SKILL.md` | `agent/skills/vault-onboard/SKILL-v1.0.md` | `scripts/vault_onboard.py` | Puebla un vault desde un proyecto de código que no tiene ninguno |
| `vault-toolkit-audit` | v1.0 | `agent/skills/vault-toolkit-audit/SKILL.md` | — | `scripts/vault_toolkit_audit.py` | Mide el toolkit tool por tool contra lo que declara y deja la medición registrada |

Las cuatro están en la wheel: instalado el paquete, se invocan como
`vault run vault_<nombre> …` con los mismos argumentos que el script.

Las tres primeras cubren los tres recorridos que el estándar reconoce —poblar
un vault, sanar uno que ya existe, documentar el estándar sobre el que se
apoyan—, y ese es el criterio para que exista una skill y no solo una tool:
**hay skill donde hay un procedimiento que un agente tiene que decidir**, no
donde hay un comando que ejecutar.

La cuarta (`vault-toolkit-audit`) es un recorrido de otro tipo: el que decide
**si el toolkit hace lo que declara**. Sin ella, medir el catálogo era una
actividad de una persona —leer el informe, decidir qué congelar, cuándo
recongelar— que cada vez se hacía de otra manera; con ella, el procedimiento
—barrido completo, veredicto por tool, baseline que solo encoge, informe
derivado— queda escrito y es el mismo para quien lo ejecute.

Durante cuatro versiones hubo una sola —`vault-sdd-init`, la periférica— mientras
los dos recorridos centrales vivían en `docs/MODO-AGENTICO-SANACION.md` y
`docs/MODO-AGENTICO-ONBOARDING.md` como prosa que el agente tenía que leer y
decidir por su cuenta. Un procedimiento que solo existe en un documento se
ejecuta distinto cada vez, y la decisión de qué fase aplicaba no quedaba escrita
en ningún sitio.

### Instalación

Una skill vive en **dos piezas** y ambas tienen que estar presentes:

| Pieza | Ruta | Para qué |
|---|---|---|
| **Definición** | `agent/skills/<nombre>/SKILL.md` | Lo que el agente descubre e invoca (`/<nombre>`). Frontmatter con `name`, `description`, `allowed-tools`, `argument-hint`. |
| **Entry point** | `scripts/vault_<nombre>.py` | El código real. La definición sin script es una tool alucinada (AP-01/AP-04). |

**No hay paso de instalación.** El descubrimiento es por convención de ruta:
un agente que abre este repo encuentra `agent/skills/` automáticamente. No se
copia nada, no se registra nada, no hay comando de install.

```bash
# Verificar qué skills ve un agente en este repo
ls agent/skills/*/SKILL.md

# Verificar que cada definición tiene su entry point
python -m pytest tests/test_vault_sdd_init.py -q
```

**Para usar la skill en otro repo** hay dos caminos, y la elección importa:

1. **CLI instalada** (recomendado) — `pip install` del paquete y nada que copiar:
   ```bash
   vault run vault_sdd_init --vault-root . --bilingual
   ```
   O, desde un checkout del estándar, el script directo:
   ```bash
   python /ruta/al/spec-repo/scripts/vault_sdd_init.py --vault-root . --bilingual
   ```
2. **Copiar `agent/skills/vault-sdd-init/`** al otro repo — solo si ese repo
   también tiene los `scripts/`. Copiar la definición sin el script produce una
   skill que falla al invocarse.

> **Regla del repo:** las tools **no se propagan** a otros repos salvo petición
> explícita del usuario. Sincronizar una skill a un vault consumidor es una
> decisión suya, no un efecto colateral de un cambio aquí.

### Gestión

**Ciclo de vida de una skill** — el mismo que el de cualquier norma del repo:
`registro canónico → doc derivada → guard que falla si divergen → test`.

| Operación | Cómo |
|---|---|
| **Añadir** | Crear `scripts/vault_<x>.py` **primero**, luego `agent/skills/<x>/SKILL.md`, luego la fila en la tabla de arriba, luego el test. Nunca al revés. |
| **Modificar argumentos** | Cambiar el `argparse` del script y sincronizar `argument-hint` + tabla de argumentos del `SKILL.md`. Divergir aquí es AP-01. |
| **Retirar** | **No se borra.** Se anota `superseded_by:` conservando el contrato (política de no-derogación). Ver `SKILL_MANIFEST` en `vault_sdd_init.py` como ejemplo real de constante conservada y anotada. |
| **Versionar** | Una reescritura de la definición sube `version:` en el frontmatter del `SKILL.md` y la columna de arriba, y la definición anterior se queda al lado como `SKILL-v<x>.md` — no se borra. Solo `SKILL.md` se descubre como skill; el archivo es historia. `tests/test_skills_versionadas.py` falla si la versión del frontmatter y la de esta tabla divergen, si una versión sube sin archivar la anterior o si la tabla de argumentos no es exactamente la del `argparse`. |
| **Verificar alineación** | `python scripts/vault_sdd_init.py --dry-run` reporta `missing_norms` y la versión detectada. Un `missing_norms` no vacío significa que el registro tiene huecos. |

**Contención (AP-36):** `--vault-root` apunta al vault destino y **toda** la
escritura ocurre bajo `<vault-root>/docs/sdd/`. La skill es read-only sobre el
resto del vault. Sin `--vault-root` se usa la autodetección de `vault_io`, que
en este repo resuelve a `vault-sandbox/`.

---

## Tool Skills — Comandos del Toolkit

> Las **tool skills** son capacidades invocables como comandos de shell. Cada una
> tiene un propósito, una interfaz de argumentos y un contrato de salida.
> A diferencia de las procedure skills (sdd-init, sanacion, onboard), una tool skill
> es un comando que se ejecuta directamente.

### Cómo invocar una tool

**CLI instalada** (`pip install -e .`):

```bash
vault tools list                         # todas las tools del catálogo
vault tools show vault_gobernanza        # detalle de una tool
vault run vault_audit                   # ejecutar una tool
```

Las tools que contestan en prosa (el catálogo las publica como
`json_flag`) devuelven su envelope con `--json`; lo pide solo la CLI de
producto y el servidor MCP, no hace falta pasarlo a mano.


**Script directo** (sin instalación):

```bash
python scripts/vault_<nombre>.py --help
```

**Módulo Python** (para integración):

```bash
python -m vault.gobernanza.tool --content "..." --vault-root /ruta/al/vault
```

### Tool Skills disponibles

| Tool Skill | Comando | Descripción |
|---|---|---|
| `vault_gobernanza` | `vault_gobernanza --content "..."` | Valida contenido contra normas MCP (secret scan, content gate, brackets, Mermaid) |
| `vault_audit` | `vault_audit` | Health check del vault |
| `vault_init` | `vault_init` | Bootstrap completo del vault |
| `vault_query_parse` | `vault_query_parse --query "..."` | Parser de consultas de contexto |
| `vault_quality_check` | `vault_quality_check` | Calidad de datos (DQ score) |
| `vault_norms` | `vault_norms --audit` | Auditoría de normas AP/PAT/SP/CN |
| `vault_fundamentals` | `vault_fundamentals --framework` | Marco CIA, FAIR, ISO |

### Gestión de tools

| Operación | Cómo |
|---|---|
| **Listar todas** | `vault tools list` |
| **Ver detalle** | `vault tools show <tool>` |
| **Documentación** | [`scripts/README.md`](../scripts/README.md) |
| **Catálogo MCP** | [`mcp/nodejs/tools-catalog.json`](../mcp/nodejs/tools-catalog.json) |

### `vault_gobernanza` v1.0

```
+---------------------------------------------+
|  GOBIERNO DEL MCP                            |
|  Pre-flight validation gate                  |
+---------------------------------------------+

Purpose:    Valida contenido contra las normas de
            gobernanza del MCP antes de escribir.

Invocación:
  vault_gobernanza --content "..." [--folder FOLDER]
  python -m vault.gobernanza.tool --content "..."
  vault run vault_gobernanza --content "..."

Inputs:
  --content  Contenido a validar (requerido)
  --folder   Carpeta destino (path-anchored links)
  --vault-root  Ruta al vault (opcional, auto-detecta)
  --format   json | text (default: text)
  --trace    Incluir trace de validación

Outputs:
  {ok: true|false, message: "...", tool: "vault_gobernanza"}

Constraints:
  - No escribe en el vault
  - Secret scan: AWS keys, GitHub tokens, passwords
  - Content gate: mínimo 3 líneas, 10 palabras
  - Bracket balance: [[...]], [...], (...), {...}
  - Mermaid: graph type válido y braces balanceados

Tests:
  python -m vault.gobernanza.tool --content "..."
```

---

## Vault como Skill — Usar Este Repo como Vault

Este repositorio **es** un vault funcional. Puedes usarlo directamente o
copiar su estructura a tu proyecto.

### Usarlo sin instalar

```bash
git clone https://github.com/devcicm/Vault-Obsidian-Architecture.git
cd Vault-Obsidian-Architecture
export VAULT_ROOT=$(pwd)          # o auto-detecta vault-*/
vault tools list
vault run vault_audit
```

### Instalarlo en tu proyecto

```bash
pip install -e /ruta/al/Vault-Obsidian-Architecture
export VAULT_ROOT=/ruta/al/tu-vault
vault --version
vault tools list
```

### Integrar el MCP server

El servidor que viaja dentro de la wheel y la entrada que el cliente
necesita las imprime la CLI; el registro se hace **por proyecto**, no
global (el procedimiento completo y el handshake de comprobación están en
[docs/INSTALACION-LIMPIA.md](INSTALACION-LIMPIA.md)):

```bash
vault mcp-path --root /ruta/al/tu-vault          # ruta del servidor + entrada del cliente
vault mcp-path --root <vault> --project <slug>   # con candado de proyecto
```

La entrada que imprime lleva `node`, el `VAULT_ROOT` del vault y el
`VAULT_MCP_PYTHON` del intérprete donde quedó instalada la wheel. Pegarla
en el `.mcp.json` del proyecto consumidor es todo el registro.

---

### `vault-sdd-init` v2.0

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
| `04-antipatterns.md` | Catálogo de antipatrones — rango derivado de `NORM_CATALOG` en cada ejecución. **La cifra no se escribe aquí:** codificarla a mano en la frase que afirma que se deriva es AP-05 sobre la frase que lo niega, y así estuvo un mes (`AP-01..AP-36` con el registro en `AP-01..AP-47`). Para leerla: `vault_sdd_init --check` |
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

- vault-spec >= v36.0. **La versión vigente no se escribe aquí:** su dueño es
  `vault_version.CURRENT_VERSION`, y se lee con
  `python -c "import sys; sys.path.insert(0,'scripts'); import vault_version; print(vault_version.CURRENT_VERSION)"`.
  Escrita a mano decía **v39.3** durante veintiocho versiones, en el mismo
  documento que dos párrafos más abajo explica por qué una cifra no se codifica
  en la skill. `test_version_coherence` no la veía porque vigilaba cinco sitios
  conocidos —banner, badge, `pyproject`, sandbox, CLI— y `docs/` no era ninguno:
  alcance declarado más ancho que el recorrido, que es el defecto que
  `vault_produccion` existe para nombrar. Desde v40.32 lo barre un test.
- `NORM_CATALOG` legible — **83 normas** hoy. El desglose por familia tampoco se
  escribe aquí: se leía «37 AP + 6 PAT + 3 SP + 3 CN», que suma 49 y no 59, y
  las puertas lo dejaron pasar porque `vault_doc_counts` vigila el total y no
  el desglose. Ni el rango ni el conteo se codifican en la skill: se derivan
  del registro, y `vault_sdd_init --check` falla si el disco se queda atrás.
- `atomic_write_text` con fix de temp leak (FASE 0.4)
- CI workflow activo
- Secret scanning operativo

> **Estado del drift:** `missing_norms: []`. El chequeo de contiguidad destapó
> `AP-26..AP-30` — cinco normas **aplicadas por `vault_audit` desde v30** pero
> nunca registradas en `NORM_CATALOG`. Quedaron registradas en v39 sin alterar
> el comportamiento del audit. Un `missing_norms` no vacío en el futuro
> significa lo mismo: enforcement en código sin entrada canónica.

#### Tests

- `tests/test_vault_sdd_init.py` — generadores, drift, idempotency.
- `tests/test_skills_versionadas.py` — versión de la definición ↔ `SKILL_VERSION` del script ↔ esta doc, y tabla de argumentos ↔ `argparse`.
- `tests/test_skills_contract.py` — contrato definición ↔ entry point ↔ doc.

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

### `vault-sdd-init` v2.0

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