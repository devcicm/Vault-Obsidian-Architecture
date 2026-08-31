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

| Skill | Versión | Definición | Entry point | Descripción |
|---|---|---|---|---|
| `vault-sdd-init` | v1.0 | `agent/skills/vault-sdd-init/SKILL.md` | `scripts/vault_sdd_init.py` | Inicializa el SDD (Spec-Driven Development documentation) de un vault |
| `vault-sanacion` | v1.0 | `agent/skills/vault-sanacion/SKILL.md` | `scripts/vault_sanacion.py` | Diagnostica un vault preexistente y devuelve el plan de 12 fases con veredicto y evidencia. **No escribe** |
| `vault-onboard` | v1.0 | `agent/skills/vault-onboard/SKILL.md` | `scripts/vault_onboard.py` | Puebla un vault desde un proyecto de código que no tiene ninguno |

Las tres cubren los tres recorridos que el estándar reconoce, y ese es el
criterio para que exista una skill y no solo una tool: **hay skill donde hay un
procedimiento que un agente tiene que decidir**, no donde hay un comando que
ejecutar. `vault-onboard` pobla desde cero, `vault-sanacion` toma un vault que
ya existe, `vault-sdd-init` documenta el estándar sobre el que se apoyan.

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

1. **Invocación directa del script** (recomendado) — no se copia nada:
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
| **Verificar alineación** | `python scripts/vault_sdd_init.py --dry-run` reporta `missing_norms` y la versión detectada. Un `missing_norms` no vacío significa que el registro tiene huecos. |

**Contención (AP-36):** `--vault-root` apunta al vault destino y **toda** la
escritura ocurre bajo `<vault-root>/docs/sdd/`. La skill es read-only sobre el
resto del vault. Sin `--vault-root` se usa la autodetección de `vault_io`, que
en este repo resuelve a `vault-sandbox/`.

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
- `NORM_CATALOG` legible — **74 normas** hoy. El desglose por familia tampoco se
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

- `tests/test_vault_sdd_init.py` — 15 tests cubriendo generadores, drift, idempotency.
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