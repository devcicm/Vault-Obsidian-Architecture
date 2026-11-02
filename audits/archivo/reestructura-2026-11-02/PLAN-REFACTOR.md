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
| A-2 | H-08 | **hecho** (`428c895`, cierre A en `52252b3`) · PURE_REFACTOR | `install`/`uninstall::_run` pasan a un único lanzador en `vault/kernel` o en el dueño de procesos. `clones-baseline` queda saldada. | `superficie` + `envelopes` |
| A-3 | H-02 | **bloqueado → replaneado tras C-2** (ver «Obstáculos del bloque A») | `vault_io` deja de importar `vault_section_index` y `vault_tags`: recibe el registro por el puerto `RegistroSecciones` de `vault/kernel/puertos.py`, que se inyecta al importarse el productor. `ciclos-baseline` pasa de 3 a 0. | `envelopes` (todas las tools que escriben notas) |
| A-4 | H-03 | **bloqueado → replaneado tras C-2** (ver «Obstáculos del bloque A») | `vault_errors._inject_voice` llama a un puerto `Voz` con `None` por defecto. `vault.autoria.voz` se registra al importarse. El cruce kernel→autoria desaparece de `PRESUPUESTO_DE_CRUCES` y pasa a `saldada`. | `envelopes` (los errores conservan su campo de voz) |
| A-5 | H-11 | **hecho** (`b883083`), ruta B ratificada el 2026-11-01 · COMPATIBLE_EVOLUTION. Antes: «bloqueado: decisión del propietario» (ver «Obstáculos del bloque A») | Se quita el cruce gobernanza→meta_toolkit, que está declarado `a_eliminar`. | `superficie` |

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
  - **El instrumento ya está (2026-11-02, `96346d5`):** `paridad.py` tiene el componente `escritos`, que mide el digest de lo que cada línea deja escrito en todo su destino (vault, casa y trabajo). Su prueba de sensibilidad está hecha: alterando el contenido de una nota del sandbox —mismo path, otro cuerpo— `envelopes` sale verde y `escritos` sale rojo nombrando el fichero. A-3 y A-4 ya no tienen su obstáculo de medida: solo queda la raíz de composición de C-2 tanda 2.
- **A-5 es decisión del propietario.**
  - El registro lo dice: «PENDIENTE DE RATIFICACIÓN DEL PROPIETARIO».
  - Las tres opciones son (A) componer desde el meta-toolkit, (B) un dueño con puerto declarado y (C) una excepción formal con plazo.
  - Medido hoy, el único sitio vivo del par es `vault/gobernanza/tool.py::_create_gobernanza` → `vault.meta_toolkit.catalog_adapter`. Es la raíz de composición de la tool `vault_gobernanza`, que ya recibe catálogo y normas por inyección.
  - El texto del cruce sigue describiendo `vault_norms` → `vault_mcp_catalog`/`vault_smoke`, que pasaron al puerto de controles en R22 (B-08).
- **La dependencia de orden «H-02/H-03 antes de H-04» no se sostiene medida.** Ninguno de los ocho módulos de B-1 y B-2 importa `vault_io`, `vault_errors`, `vault_section_index`, `vault_tags` ni `autoria`. El bloque B no arrastra ningún ciclo y puede ir antes.

## Bloque B — núcleo (riesgo medio)

| Paso | Hallazgo | Clase | Qué cambia | Paridad |
|---|---|---|---|---|
| B-1 | H-04 | **hecho** (cierre en `CHANGELOG-REFACTOR.md`, `aa93254`) · PURE_REFACTOR — **replaneado** (ver «Obstáculos del bloque B»): subpaquete `vault/kernel/normativa/`, dentro del contexto kernel | ~~Contexto nuevo `vault/normativa/` con `norms_catalog`, `fundamentals_catalog`, `audit_catalog`, `mermaid_reglas`, `contrato_nota` y `vocabulario`. Cada uno se mueve en un commit propio. El viejo `vault/kernel/<x>.py` queda como alias `sys.modules` con `superseded_by`. `vault_arch` declara el contexto; `vault_kernel --check` y AP-59 se recalculan.~~ Los seis se mueven a `vault/kernel/normativa/`, un commit por módulo. El viejo `vault/kernel/<x>.py` queda como alias `sys.modules` con `superseded_by`. Los alias de `scripts/` y los consumidores internos apuntan al dueño nuevo. `vault_arch` no cambia: siguen siendo del contexto kernel. | `superficie` (los nombres no cambian) + `estatico` |
| B-2 | H-04 | **hecho: NOT_APPLICABLE** (medido sobre `4d9d031`, ver «Obstáculos del bloque B») · ~~PURE_REFACTOR~~ | ~~`registry` y `proyectos` se mueven al contexto que los consume (se decide midiendo el fan-in en el momento del paso).~~ Nada: no hay un contexto que los consuma por encima del resto. | no aplica: no hay código tocado |
| B-3 | H-05 + C-07 | **hecho** (filas en `CHANGELOG-REFACTOR.md`, `e857417` a `c798268` y el cierre sobre `fb7f17e`; `carriles`, `perfil_suite` y `test_scope` en un solo commit, porque `test_scope` importa a los otros dos) · COMPATIBLE_EVOLUTION — **replaneado** (ver «Obstáculos del bloque B»): subpaquete `vault/meta_toolkit/estandar/`, fuera de la wheel | ~~Contexto `gobernanza_del_estandar`, que recibe `carriles`, `perfil_suite`, `test_scope`, `firma_sitio`, `spec_catalog_check` y `kernel/baseline.py`. Queda fuera de la wheel y la exclusión la vigila `vault_produccion`. Los alias en `meta_toolkit` se conservan.~~ Primero el mecanismo: `vault_servicio` declara el subpaquete y deriva sus alias a `empaquetado/fuera-de-la-wheel.json`, el hook de `construir.py` los filtra y `check_de_la_wheel` falla si algo que viaja importa al subpaquete. Después `carriles`, `perfil_suite`, `firma_sitio`, `spec_catalog_check` y `test_scope` se mueven a `vault/meta_toolkit/estandar/`, un commit por módulo. El viejo `vault/meta_toolkit/<x>.py` queda como alias `sys.modules` con `superseded_by` (con `runpy` si el módulo tiene `__main__`). `kernel/baseline.py` y `test_runner` se quedan donde están. | `superficie` + `estatico` + test de contenido de la wheel |

### Obstáculos del bloque B (2026-10-31, al ejecutarlo)

- **B-1 como contexto aparte rompe una frontera que ya se había arreglado.**
  - Los seis catálogos forman una pieza cerrada: solo dependen entre ellos, de `vault_registry` y de `vault_grafo_import`, todos del kernel.
  - Pero los consumen casi todos los contextos:

    | Catálogo | Consumidores | Contextos |
    |---|---|---|
    | `norms_catalog` | 37 | 7 |
    | `vocabulario` | 21 | 7 |
    | `fundamentals_catalog` | 12 | 4 |
    | `contrato_nota` | 11 | 4 |
    | `audit_catalog` | 7 | 3 |
    | `mermaid_reglas` | 3 | 3 |

  - Como contexto de dominio, `normativa` estrenaría 6 pares de cruce (autoria, ciclo_de_vida, consulta, gobernanza, grafo y meta_toolkit → normativa). `vault_arch --check` se pondría en rojo.
  - Además, deshace lo que v40.27–28 arregló a propósito (AP-62): 22 de los 62 cruces de entonces eran tools leyendo una tabla constante.
  - En DDD, un modelo que comparten todos los contextos es *shared kernel* por definición. El defecto de H-04 no es que estén en el núcleo, sino que el núcleo mezcla en el mismo directorio la infraestructura (raíz, fs, escritura, procesos) con el lenguaje compartido.
  - **Decisión del propietario (2026-10-31):** subpaquete `vault/kernel/normativa/`. Separa las dos cosas en disco sin cambiar ninguna frontera. La alternativa de declarar un segundo shared kernel en `vault_arch` queda como candidata.
- **B-2 merece la misma pregunta antes de ejecutarse.** `vault_registry` tiene 44 consumidores en 8 contextos, y `proyectos` entró al kernel desde autoria en v40.34 (AP-63) precisamente porque es identidad que leen todos. Se mide en su paso, pero lo esperable es NOT_APPLICABLE o subpaquete.
  - **Medido al ejecutarlo (sobre `4d9d031`, imports AST de `scripts/`, `vault/`, `cli/`, `vault_toolkit/` y `normas/`, contexto según `vault_arch.contexto_de`):**

    | Módulo | Consumidores | Contextos | Mayor consumidor |
    |---|---|---|---|
    | `registry` | 47 | 9 | autoria, 21 |
    | `proyectos` | 21 | 5 (kernel incluido) | autoria, 12 |

  - Llevar `registry` a autoria estrenaría tres pares que `PRESUPUESTO_DE_CRUCES` no tiene: gobernanza → autoria, meta_toolkit → autoria e indices → autoria. `vault_arch --check` se pondría en rojo.
  - Llevar `proyectos` a autoria devuelve el sitio de donde salió en v40.34 (AP-63) y deja a `vault_errors` cruzando de kernel a autoria, que es el cruce que C-1 quiere eliminar.
  - **Resultado: NOT_APPLICABLE**, como A-1. Los dos son *shared kernel* por la misma razón que los seis de B-1.
  - Queda como CANDIDATE meter `registry` en `vault/kernel/normativa/`. Es lenguaje compartido (secciones y clase de documento), pero no es hoja: importa `vault_grafo_import`. Ante la duda no se ejecuta. `proyectos` no es candidato, porque escribe (`escritura_atomica`) y resuelve identidad: es servicio, no vocabulario.

- **B-3 como contexto aparte tiene el mismo problema que B-1, y dos de sus piezas no pueden salir de la wheel.**
  - **Decisión del propietario (2026-10-31):** subpaquete `vault/meta_toolkit/estandar/`, dentro del contexto `meta_toolkit` y excluido de la wheel. `vault_arch` no cambia. El precedente es v40.34, que ya sacó de la wheel los scripts del grupo 35 con `empaquetado/fuera-de-la-wheel.json`, derivado por `vault_servicio --wheel-sync`.
  - **Medido sobre `be613d2`** (imports AST y menciones literales en `scripts/`, `vault/`, `cli/`, `vault_toolkit/` y `mcp/nodejs/`, sin contar lo que ya está fuera de la wheel). En lo que viaja, los cinco módulos solo aparecen en comentarios o en cadenas: `perfil_suite` y `spec_catalog_check` en `vault_mcp_catalog`, `vault_spec_catalog_check.py` en el conjunto `_META_FILES` de `cli/analyzer.py`, `vault_test_scope` en `INTERNAL_TOOLS` de `vault_spec_data` y `vault_firma_sitio` en el docstring de `kernel/baseline.py`. Sus importadores reales (`vault_gate`, `vault_tests_higiene`, `vault_blame_audit`, `vault_error_contract`, `vault_excepcion_declarada`, `vault_fix_all`, `vault_produccion`, `vault_arch` y `vault_blueprint`) ya están fuera.
  - **`kernel/baseline.py` se queda en el núcleo y en la wheel.** La importa `vault.gobernanza.fuente_unica`, que es la tool de producto `vault_fuente_unica` («Salud del Vault»).
  - **`test_runner` se queda en `meta_toolkit` y en la wheel** (no estaba en la lista original, pero era el sexto candidato del recuento). Ningún módulo que viaja lo importa, pero `vault_spec_memory`, que viaja, lo lanza como subproceso por su ruta (`SCRIPTS_DIR / "vault_test_runner.py"`), y `vault_spec_data` lo cuenta en `META_TOOLS`. Medir solo los imports lo habría dado por suelto. Ante la duda no se mueve: queda como CANDIDATE.
  - **Los alias también salen.** Un alias de `scripts/` o de `meta_toolkit` cuyo dueño no viaja daría `ImportError` en la instalación, y no lo importa nadie de lo que viaja. Salen con su dueño y el guard comprueba las dos cosas.

## Bloque C — inyección de la raíz (riesgo alto, el más valioso para la suite)

| Paso | Hallazgo | Clase | Qué cambia | Paridad |
|---|---|---|---|---|
| C-1 | H-09 | **hecho** (cierre en `CHANGELOG-REFACTOR.md`, carril `merge` el 2026-11-01) · COMPATIBLE_EVOLUTION — **la baseline por firma no hizo falta**: el guard extendido (la llamada a `get_vault_root()` al importar también congela el vínculo) mide **0** vínculos; la migración previa no dejó nada que congelar. `_reanclar_constantes` queda como compatibilidad. | Guard nuevo: ninguna constante `Path` nueva derivada de la raíz al importarse. Lleva baseline por firma, que hoy recoge los 89 módulos y solo encoge. Se lo tomó el guard como su hueco: la asignación `X = get_vault_root() / "a"` era la misma deuda con otra sintaxis y no la veía. Eximido solo lo tarde de verdad: el cuerpo de una función y la lambda. | ninguna salida cambia —verificado: ningún delta nuevo en `estatico`, `superficie`, `ayuda` ni envelopes frente a lo ya declarado de tablones previos |
| C-2 | H-10 | **tanda 1 hecha** (`10ffe47`, fila en `CHANGELOG-REFACTOR.md`): helper canónico `correr_en_proceso` en `tests/apoyo.py`; los ejemplos AP-42 y el barrido de flags desconocidos corren en proceso, el contrato CLI conserva un subproceso por tool. **Medido al ejecutarla:** 3 de los 6 módulos del perfil ya corrían en proceso — su tiempo es cómputo y contención, no subproceso. La forma `ejecutar(ctx: VaultContext, args)` y el lanzamiento en proceso de las ~15 tools que `fix_all`/`noop_audit` orquestan internamente quedan para la tanda 2, decidida contra la medida conjunta. | Las tools de más subprocesos en la suite (las elige el perfil) exponen `ejecutar(ctx: VaultContext, args)` y su `main()` solo construye el contexto. Los tests de esas tools pasan a ejecución en proceso. Los tests de contrato CLI conservan un subproceso por tool. | spans de `comandos_publicados` 86→34.5 s y de `ap52` 69→52 s; envelopes + ayuda intactos |

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
