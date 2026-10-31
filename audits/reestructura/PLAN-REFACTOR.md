# Plan de refactor — tablones de la fase 3

**Precondiciones, las tres a la vez:**
- árbol limpio en `reestructura/teseo`;
- golden master capturado en `golden/` (`paridad.py --capturar`);
- suite completa en verde en el commit de partida, con el recuento en `golden/suite.json`.

**Cada tablón termina así:**
1. un commit propio;
2. el carril `dev` en verde;
3. `python -B audits/reestructura/paridad.py --comparar` en verde;
4. las puertas `rapida` en verde;
5. una fila en `CHANGELOG-REFACTOR.md` con el hash.

Al cerrar cada bloque se corre el carril `merge`, en serie.

**Cuánto cuesta la paridad, medido el 2026-10-31:**

| Comando | Qué compara | Tiempo | Cuándo |
|---|---|---|---|
| `paridad.py --comparar --solo estatico,superficie,ayuda` | catálogos y `schemas/`, 301 módulos, 128 `--help` | unos 40 s | cada tablón |
| `paridad.py --comparar --tools <las que toca el tablón>` | envelopes de esas tools | segundos por tool | cada tablón |
| `paridad.py --comparar` | todo, 126 tools y 233 líneas | unos 15 min | al cerrar cada bloque |

**Riesgo medido.** Algunas tools leen la historia de git (`vault_changelog_check`,
`vault_init`), y se temía que rompieran la paridad en cada commit. La primera
comparación completa tras el commit de la auditoría (`bad1750`) lo descartó: las dos
quedaron en verde. Lo que sí salió rojo fueron tres hashes sobre contenido con la hora
del alta de `mi-api` (`merkle_root` de `vault_backup#0/#1` y `source_sha` de
`vault_graph_fix#0`). No era una regresión: el detector de volátiles compartía el
vault de origen entre las dos repeticiones y no podía verlos variar. Se arregló el
instrumento (cada repetición construye su origen) y se recapturó solo `envelopes`, como
operación explícita fuera de un tablón. El golden nuevo es idéntico al anterior fuera
de los volátiles. Esos pasan de 12 a 14 corridas: los tres hashes y `segundos` de
`vault_toolkit_audit#0`, que es una duración.

**Mientras corre `paridad.py` no se edita nada del repo.** `CustodiaDelRepo` tomaría la
edición por una escritura de una tool y la desharía.

**Si un tablón rompe la paridad:** se revierte, se anota el obstáculo y se replanea. No
se recaptura el golden para que pase.

Solo entran aquí hallazgos CONFIRMED que son PURE_REFACTOR o COMPATIBLE_EVOLUTION, y
los COMPATIBLE_EVOLUTION entran porque la persona pidió la reestructura. Los candidatos
siguen en `AUDITORIA.md`.

## Bloque A — redundancia y ciclos (riesgo bajo o medio)

| Paso | Hallazgo | Clase | Qué cambia | Paridad que lo cubre |
|---|---|---|---|---|
| A-1 | H-01 | ~~COMPATIBLE_EVOLUTION~~ **descartado**: al deconstruirlo resultó NOT_APPLICABLE (ver H-01). No se toca código. | `vault/meta_toolkit/tools-catalog.json` queda como fuente única. `mcp/nodejs/tools-catalog.json` sigue existiendo como derivado: `--sync` lo escribe y `--check` exige igualdad. Se declara en `DERIVADOS`, para que nadie lo edite pensando que es la fuente. | `estatico` (los dos hashes no cambian) |
| A-2 | H-08 | PURE_REFACTOR | `install`/`uninstall::_run` pasan a un único lanzador en `vault/kernel` o en el dueño de procesos. `clones-baseline` queda saldada. | `superficie` + `envelopes` |
| A-3 | H-02 | **bloqueado → replaneado tras C-2** (ver «Obstáculos del bloque A») | `vault_io` deja de importar `vault_section_index` y `vault_tags`: recibe el registro por el puerto `RegistroSecciones` de `vault/kernel/puertos.py`, que se inyecta al importarse el productor. `ciclos-baseline` pasa de 3 a 0. | `envelopes` (todas las tools que escriben notas) |
| A-4 | H-03 | **bloqueado → replaneado tras C-2** (ver «Obstáculos del bloque A») | `vault_errors._inject_voice` llama a un puerto `Voz` con `None` por defecto. `vault.autoria.voz` se registra al importarse. El cruce kernel→autoria desaparece de `PRESUPUESTO_DE_CRUCES` y pasa a `saldada`. | `envelopes` (los errores conservan su campo de voz) |
| A-5 | H-11 | **bloqueado: decisión del propietario** (ver «Obstáculos del bloque A») | Se quita el cruce gobernanza→meta_toolkit, que está declarado `a_eliminar`. | `superficie` |

### Obstáculos del bloque A (2026-10-31, al ejecutarlo)

Resultado del bloque: A-1 descartado (NOT_APPLICABLE), A-2 hecho (`428c895`) y A-3, A-4 y A-5 bloqueados.
Ninguno de los tres se forzó.
El carril `merge` lo cerró sobre `52252b3`, con la paridad completa, las 28 puertas y la suite en verde. El detalle está en la fila «cierre A» de `CHANGELOG-REFACTOR.md`.

- **A-3 y A-4 necesitan una raíz de composición que hoy no existe.**
  - `vault_io` dispara el índice de sección y la bitácora de tags en cada escritura de nota.
  - `vault_errors` pone `vault_says` en cada envelope.
  - Las dos cosas valen para todas las tools, también para las que nunca importan `vault_section_index`, `vault_tags` o `vault.autoria.voz`.
  - Si el productor se registra al importarse, esas tools pierden el gancho en silencio, y eso cambia C(P).
  - Si el kernel resuelve el productor por nombre (`importlib`), el import diferido se queda donde está pero AP-58 no lo ve. Eso es esconder el ciclo, no romperlo.
  - Además, el puerto que proponía el plan (`RegistroSecciones`) da los nombres de sección y no regenera índices. No encaja.
  - **Lo que falta medir:** el golden compara envelopes, no los ficheros que la tool deja en el vault. En A-3 una regresión sería invisible para `paridad.py`, que es el punto ciego que AP-44 nombra.
  - **Replan:** van detrás de C-2. Cuando cada tool construye su `VaultContext` en `main()`, ese `main()` es la raíz de composición. Allí se inyectan el regenerador de índices y la voz, con el valor por defecto que hoy da el import. Antes de A-3, `paridad.py` añade una instantánea de los ficheros escritos por corrida.
- **A-5 es decisión del propietario.**
  - El registro lo dice: «PENDIENTE DE RATIFICACIÓN DEL PROPIETARIO».
  - Las tres opciones son (A) componer desde el meta-toolkit, (B) un dueño con puerto declarado y (C) una excepción formal con plazo.
  - Medido hoy, el único sitio vivo del par es `vault/gobernanza/tool.py::_create_gobernanza` → `vault.meta_toolkit.catalog_adapter`. Es la raíz de composición de la tool `vault_gobernanza`, que ya recibe catálogo y normas por inyección.
  - El texto del cruce sigue describiendo `vault_norms` → `vault_mcp_catalog`/`vault_smoke`, que pasaron al puerto de controles en R22 (B-08).
- **La dependencia de orden «H-02/H-03 antes de H-04» no se sostiene medida.** Ninguno de los ocho módulos de B-1 y B-2 importa `vault_io`, `vault_errors`, `vault_section_index`, `vault_tags` ni `autoria`. El bloque B no arrastra ningún ciclo y puede ir antes.

## Bloque B — núcleo (riesgo medio)

| Paso | Hallazgo | Clase | Qué cambia | Paridad |
|---|---|---|---|---|
| B-1 | H-04 | PURE_REFACTOR | Contexto nuevo `vault/normativa/` con `norms_catalog`, `fundamentals_catalog`, `audit_catalog`, `mermaid_reglas`, `contrato_nota` y `vocabulario`. Cada uno se mueve en un commit propio. El viejo `vault/kernel/<x>.py` queda como alias `sys.modules` con `superseded_by`. `vault_arch` declara el contexto; `vault_kernel --check` y AP-59 se recalculan. | `superficie` (los nombres no cambian) + `estatico` |
| B-2 | H-04 | PURE_REFACTOR | `registry` y `proyectos` se mueven al contexto que los consume (se decide midiendo el fan-in en el momento del paso). | ídem |
| B-3 | H-05 + C-07 | COMPATIBLE_EVOLUTION | Contexto `gobernanza_del_estandar`, que recibe `carriles`, `perfil_suite`, `test_scope`, `firma_sitio`, `spec_catalog_check` y `kernel/baseline.py`. Queda fuera de la wheel y la exclusión la vigila `vault_produccion`. Los alias en `meta_toolkit` se conservan. | `superficie` + test de contenido de la wheel |

## Bloque C — inyección de la raíz (riesgo alto, el más valioso para la suite)

| Paso | Hallazgo | Clase | Qué cambia | Paridad |
|---|---|---|---|---|
| C-1 | H-09 | COMPATIBLE_EVOLUTION | Guard nuevo: ninguna constante `Path` nueva derivada de la raíz al importarse. Lleva baseline por firma, que hoy recoge los 89 módulos y solo encoge. `_reanclar_constantes` queda como compatibilidad. | ninguna salida cambia |
| C-2 | H-10 | COMPATIBLE_EVOLUTION | Las tools de más subprocesos en la suite (las elige el perfil) exponen `ejecutar(ctx: VaultContext, args)` y su `main()` solo construye el contexto. Los tests de esas tools pasan a ejecución en proceso. Los tests de contrato CLI conservan un subproceso por tool. | `envelopes` + `ayuda` |

## Bloque D — dioses (riesgo medio, el último)

| Paso | Hallazgo | Clase | Qué cambia | Paridad |
|---|---|---|---|---|
| D-1 | H-06 | PURE_REFACTOR | `vault_mcp_catalog` se parte en datos y motor. Los datos van a `vault/meta_toolkit/catalogo_datos.py` y el script conserva la CLI y los nombres. | `estatico` + `superficie` + `envelopes` |
| D-2 | H-06 | PURE_REFACTOR | `vault_blueprint`, partido igual en datos y motor. | ídem |
| D-3 | H-06 | PURE_REFACTOR | `vault_arch`, `vault_audit` y `vault_onboard`: el motor va a su contexto en `vault/` y el script queda como alias más CLI. | ídem |

## P4 — no se ejecutan en esta rama

- C-01 a C-07: siguen como candidatos hasta que haya medida.
- `AGENTS.md` estable, sacando los bloques derivados a `docs/`. Es documentación, no estructura, y va aparte tras el bloque D.
- B-02, B-04 y B-05 (BUGS): son FIX, en commits propios fuera de los tablones, si la persona los autoriza.
