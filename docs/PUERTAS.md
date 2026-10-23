# Las puertas de cierre y por qué existe cada una

> **Derivado.** Sale de `vault_gate.PUERTAS` y del docstring de cada tool;
> se regenera con `python scripts/vault_gate.py --fix-doc` y `--check-doc`
> falla si diverge. Lo escrito a mano aquí se pierde: el porqué se corrige
> en el docstring de la tool.

Puertas: 26. Verde en todas no es verde en la suite.

## `framework`

- **Comando:** `python scripts/vault_norms.py --check-framework`
- **Mide:** El manifiesto documenta todo id del marco de datos y toda norma catalogada tiene sección propia.

**Vault Norms — la puerta de entrada al catálogo de normas del estándar.**

Gestiona AP-XX (anti-patrones) y PAT-X (patrones recomendados): lista, filtra, muestra detalles, escanea notas para detectar normas aplicables, aplica referencias de normas a frontmatter, y reconstruye norm-registry.json.

## `catalogo`

- **Comando:** `python scripts/vault_mcp_catalog.py --check`
- **Mide:** El catálogo Python y tools-catalog.json no divergen.
- **Se arregla con:** python scripts/vault_mcp_catalog.py --sync

**Vault MCP Catalog — Catálogo canónico de tools del vault.**

Contiene la definición de todas las tools (cuántas, `len(TOOLS_CATALOG)`) con sus:

- Propósito
- Parámetros
- Validadores
- Guards
- Efectos secundarios
- Ejemplos
- Tools relacionadas

## `contratos`

- **Comando:** `python scripts/vault_mcp_catalog.py --check-contracts`
- **Mide:** Toda tool del catálogo tiene entrada en tool-spec.json, toda entrada que ya no está declara su status en vez de borrarse, y ninguna tool tiene a la vez backend nativo en Node y script Python (AP-48).
- **Normas:** [AP-48](../normas/AP-48/porque.md)

**Vault MCP Catalog — Catálogo canónico de tools del vault.**

Contiene la definición de todas las tools (cuántas, `len(TOOLS_CATALOG)`) con sus:

- Propósito
- Parámetros
- Validadores
- Guards
- Efectos secundarios
- Ejemplos
- Tools relacionadas

## `conteos`

- **Comando:** `python scripts/vault_doc_counts.py --check --strict`
- **Mide:** Ninguna cifra de la documentación está escrita a mano (AP-47).
- **Se arregla con:** python scripts/vault_doc_counts.py --fix
- **Normas:** [AP-47](../normas/AP-47/porque.md)

**vault_doc_counts — guard anti-drift de cifras en documentación.**

Ninguna cifra que describa el estándar debe escribirse a mano. Cada número en prosa ("81 tools activas", "48 normas", "18 carpetas estándar") es una mentira futura: se escribe una vez, deja de ser cierto en el commit siguiente y nadie lo nota porque nada lo verifica.

## `doc_sync`

- **Comando:** `python scripts/vault_doc_sync.py --check --strict`
- **Mide:** Toda tool tiene sección en scripts/README.md y el índice una fila por grupo.
- **Se arregla con:** python scripts/vault_doc_sync.py --fix  (solo el índice; las secciones se escriben a mano)

**vault_doc_sync — guard anti-drift de NOMBRES entre el registro y scripts/README.md.**

`vault_doc_counts` vigila las cifras; esta tool vigila los nombres, que es la otra mitad del mismo problema. El síntoma que la originó, medido en v39:

## `toolkit_audit`

- **Comando:** `python scripts/vault_toolkit_audit.py --check`
- **Mide:** AP-42 — el ejemplo documentado de cada tool ejercita la función que declara: corre de verdad (con el proyecto y los ficheros que el propio ejemplo da por existentes), su envelope cubre el contrato y, si promete idempotencia, la segunda corrida no reescribe nada. La puerta mide DEUDA NUEVA: la congelada en scripts/toolkit-audit-baseline.json está declarada y revisada (solo encoge; crecer exige --freeze --admitir-nuevos).
- **Se arregla con:** reparar la tool o su ejemplo; el freeze del auditor solo encoge y crecer exige --freeze --admitir-nuevos
- **Normas:** [AP-42](../normas/AP-42/porque.md)

**vault_toolkit_audit — verificación funcional del toolkit, tool por tool.**

`vault_smoke` (AP-42) mide que la herramienta corre y que su envelope tiene `ok`. Esta script mide lo que nadie más mide: que el ejemplo documentado **ejercice la función declarada** — y lo hace sobre la maquinaria ya pagada, sin substituir a ningún guard:

## `noop`

- **Comando:** `python scripts/vault_noop_audit.py --check --ejecutado --strict`
- **Mide:** AP-37 — ninguna tool con side effects devuelve ok: true sin indicador de trabajo, en lo declarado y en lo que el ejemplo emite al ejecutarse.
- **Se arregla con:** saldar la deuda y luego --freeze
- **Normas:** [AP-37](../normas/AP-37/porque.md)

**vault_noop_audit — AP-37: ninguna tool devuelve `ok: true` sin decir qué hizo.**

El síntoma que originó esta norma: `vault_standard_upgrade --to latest` devolvía `{"ok": true}` habiendo aplicado **cero** migraciones, porque `_version_index()` no normalizaba la minor version. El bug vivió versiones enteras precisamente porque la respuesta era indistinguible de un éxito real.

## `blame`

- **Comando:** `python scripts/vault_blame_audit.py --check --strict`
- **Mide:** AP-51 — ningún handler amplio devuelve un vacío indistinguible de un resultado legítimo.
- **Se arregla con:** saldar la deuda y luego --freeze
- **Normas:** [AP-51](../normas/AP-51/porque.md)

**vault_blame_audit — AP-51: la tool no acusa al dato de su propio fallo.**

El síntoma que originó esta norma salió al ejecutar contra un vault ajeno al estándar (regla 7): tres tools declaraban notas "inválidas" que Obsidian leía sin problema. La nota estaba bien. Lo que estaba mal era el criterio con el que se la medía — frontmatter por regex línea a línea en vez de `yaml.safe_load`, y wikilinks resueltos por `title:`, que Obsidian no mira. La tool falló, y el veredicto que emitió señalaba al dato.

## `contrato_error`

- **Comando:** `python scripts/vault_error_contract.py --check --strict`
- **Mide:** AP-52 — ningun envelope de error nuevo se emite fuera del contrato de ERROR_CATALOG.
- **Se arregla con:** emitir por emit_error y luego --freeze
- **Normas:** [AP-52](../normas/AP-52/porque.md)

**vault_error_contract — AP-52: el error se emite fuera del contrato del catálogo.**

Salió de la caracterización maliciosa: invocar cada tool de forma malformada y mirar **cómo** falla, no si falla. Dos sondas sobre las 94 tools —invocación vacía y flag desconocido— dejaron el grueso limpio (45/45 de las tools con `required_args` rechazan por argparse) y destaparon otra cosa:

## `campos`

- **Comando:** `python scripts/vault_spec_catalog_check.py --check-fields --strict`
- **Mide:** Contrato de campos con los repos consumidores: ningún campo estable desaparece sin quedar anotado en superseded_fields.
- **Se arregla con:** anotar el campo en superseded_fields (superseded_by + why) o volver a emitirlo; --freeze-fields solo tras revisar

**vault_spec_catalog_check — Validate sync between tool-spec.json and TOOLS_CATALOG.**

Detects:

- Tools missing from either source
- Group name mismatches
- Status mismatches (active/deprecated)

## `changelog`

- **Comando:** `python scripts/vault_changelog_check.py --check --strict`
- **Mide:** El changelog no contradice a git: hash existente, fecha igual a la del commit, ningún `pending` de una versión ya cerrada.
- **Se arregla con:** python scripts/vault_changelog_check.py --fijar-hash  (cierra la versión en curso); corregir la fecha contra su commit

**vault_changelog_check — el changelog del manifiesto, contrastado contra git.**

El changelog vive dentro de `vault-obsidian-architecture.md` y cada entrada publica el hash del commit que introdujo la versión:

## `arquitectura`

- **Comando:** `python scripts/vault_arch.py --check --strict`
- **Mide:** Contextos acotados: fronteras, puertos, vocabularios con dueño, entorno declarado, AP-49 en cero.
- **Normas:** [AP-49](../normas/AP-49/porque.md)

**Plano técnico del estándar: contextos acotados y sus fronteras.**

Los 37 grupos del catálogo son una taxonomía de documentación —sirven para encontrar una tool en `scripts/README.md`—, no fronteras de dominio. Nada dice hoy quién puede importar a quién, y por eso los defectos de v39.5 y v39.6 son todos el mismo: una capacidad implementada dos veces (AP-48), un side effect fuera del vault, cinco módulos ejecutables en ningún registro. Se detectan de uno en uno y después del hecho.

## `servicio`

- **Comando:** `python scripts/vault_servicio.py --check --strict`
- **Mide:** Trazabilidad tool → grupo → capacidad → servicio: todo grupo pertenece a una capacidad y toda capacidad tiene tool viva.
- **Se arregla con:** clasificar el grupo en la capacidad a la que sirve; si no sirve a ninguna, la pregunta es por qué existe el grupo

**vault_servicio — el pilar: qué servicio de negocio presta este estándar, y qué lo realiza.**

Este repo tenía diez registros canónicos —`CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`, `GROUPS`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY`, el `tool-spec.json` y la tabla de entorno— y ninguno decía **para qué**. Se podía responder «esta tool, ¿en qué contexto vive?» y «esta norma, ¿qué severidad tiene?», pero no «esta tool, ¿a qué servicio sirve?». Sin esa respuesta, una tool nueva no tiene contra qué justificarse y el catálogo crece por acumulación.

## `blueprint`

- **Comando:** `python scripts/vault_blueprint.py --check --strict`
- **Mide:** El plano de docs/BLUEPRINT.md no diverge de los registros, y ninguna norma estrena falta de puerta y test a la vez.
- **Se arregla con:** python scripts/vault_blueprint.py --blueprint  (regenera el plano); una norma nueva sin cobertura se cubre con un test, no se congela

**vault_blueprint — el plano de construcción: qué se construye, sobre qué, y con qué guard.**

Este repo tenía once registros canónicos —`SERVICIO`, `CAPACIDADES`, `CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`, `GROUPS`/`TOOLS_CATALOG`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY` y el `tool-spec.json`— repartidos en diez módulos y **sin nada que los atase**. Se podía responder cualquier pregunta dentro de un registro y ninguna que cruzara dos: «esta tool, ¿a qué servicio sirve?», «esta norma, ¿qué puerta la hace cumplir y qué test la muerde?». `docs/ARQUITECTURA.md` cubre una sola capa —contextos y puertos— y no pretende otra cosa.

## `norms_coherence`

- **Comando:** `python scripts/vault_norms_coherence.py --check --strict`
- **Mide:** El catálogo de normas no se contradice ni con el código que lo aplica ni con las penalizaciones que lo pesan (AP-55).
- **Se arregla con:** que el código nombre la norma en el sitio que la aplica, o que el catálogo retire la cobertura que no tiene; ampliar la baseline no es una de las dos
- **Normas:** [AP-55](../normas/AP-55/porque.md)

**vault_norms_coherence — AP-55: el catálogo de normas se certifica a sí mismo.**

`NORM_CATALOG` declara, por norma, qué tools la hacen cumplir (`tools_enforcing`) y cuáles la detectan (`tools_detecting`). Esos dos campos se escriben a mano y **nada los contrasta contra lo que las tools hacen**. El resultado medido en la tanda de v40.10: 47 afirmaciones de cobertura sin una sola línea de código que nombre la norma que dicen aplicar. `AP-05` —severidad `critical`— declara `vault_graph_inspect` como detector, y esa tool no menciona AP-05 en ninguna parte.

## `criterios`

- **Comando:** `python scripts/vault_criterios.py --check --strict`
- **Mide:** Ningún módulo que clasifica notas reescribe un criterio que ya tiene dueño canónico (AP-57).
- **Se arregla con:** importar al dueño en vez de decidir por cuenta propia; la baseline solo encoge
- **Normas:** [AP-57](../normas/AP-57/porque.md)

**vault_criterios — un criterio con dueño, reimplementado en la medida (AP-57).**

v40.12 arregló cuatro defectos de `vault_foreign_check` en una sola tanda, y los cuatro tenían la misma forma: **el registro canónico existía y la tool no lo consultaba**. Instantáneas congeladas contadas como notas; documentación del estándar contada como enlaces rotos; wikilinks dentro de un fence contados como enlaces; destinos con carpeta resueltos por basename. Cuatro parches y ninguna norma es exactamente lo que la regla 4 prohíbe: una corrección puntual sin norma que la sostenga se vuelve a romper, y aquí ya se rompió cuatro veces.

## `fuente_unica`

- **Comando:** `python scripts/vault_fuente_unica.py --check --strict`
- **Mide:** El mismo dato tipado no tiene valores distintos en varias notas del mismo ámbito (AP-05).
- **Se arregla con:** PAT-1: una nota canónica declara el dato y las demás la enlazan; verde solo cubre la parte decidible sin interpretar
- **Normas:** [AP-05](../normas/AP-05/porque.md)

**vault_fuente_unica — el mismo dato con valores distintos en varias notas (AP-05).**

AP-05 es `critical` desde v19 y estuvo sin detector hasta v40.15 — la única en esa situación, y declarada así en `cobertura_descubierta` en vez de escondida en una lista vacía. El motivo escrito era real: decidir qué es «el mismo dato» sin embeddings es un problema de diseño abierto.

## `ciclos`

- **Comando:** `python scripts/vault_ciclos.py --check --strict`
- **Mide:** Ningún ciclo de importación nuevo se esquiva metiendo el import dentro de una función (AP-58).
- **Se arregla con:** invertir la dependencia: el módulo de bajo nivel deja de pedirle el módulo entero al de alto; subir el import o ampliar la baseline no son la solución, solo esconden dónde
- **Normas:** [AP-58](../normas/AP-58/porque.md)

**vault_ciclos — el ciclo que se esquiva con un import diferido (AP-58).**

Este repo declaraba **cero ciclos de importación**, y era verdad leyendo solo los `import` de nivel de módulo. El cero estaba fabricado: 92 imports metidos dentro del cuerpo de una función, en 40 módulos. Mover un import hacia dentro es el rompe-ciclos manual, y aplicado 92 veces deja de ser una excepción para convertirse en la arquitectura — pero no aparece en ninguna medida, porque la medida solo miraba el nivel superior.

## `kernel`

- **Comando:** `python scripts/vault_kernel.py --check --strict`
- **Mide:** La lista del núcleo no contradice a la forma medida del grafo: K1 delegada, fan-in/fan-out contra el escalón derivado y churn contra la mediana del dominio (AP-59).
- **Se arregla con:** sacar el módulo del kernel o darle forma de núcleo —fan-out abajo, consumidores reales—; los umbrales se derivan del escalón y se publican, así que ajustarlos para pasar no es una opción, y la baseline solo encoge
- **Normas:** [AP-59](../normas/AP-59/porque.md)

**vault_kernel — el núcleo se declara pero nadie lo mide (AP-59).**

`vault_arch.CONTEXTS['kernel']['modulos']` es una **lista de nombres escrita a mano**. Dice cuál es el núcleo de este repo y ninguna puerta la contrasta contra nada. Es la misma clase de afirmación que AP-47 persigue en las cifras y AP-57 en los criterios, cometida en el sitio más caro: si la pertenencia al kernel está mal, `vault_arch` mide sus fronteras contra un mapa equivocado y sale verde.

## `excepcion_declarada`

- **Comando:** `python scripts/vault_excepcion_declarada.py --check --strict`
- **Mide:** Ningún handler captura la excepción que una librería declara dejando escapar la que lanza de verdad (AP-61).
- **Se arregla con:** delegar en el dueño que ya la contuvo —para el frontmatter, vault_lib.parse_frontmatter— o nombrar la excepción citando al dueño; ampliar la tupla en trece sitios sin dueño es AP-57 cometido al arreglar AP-61
- **Normas:** [AP-61](../normas/AP-61/porque.md)

**vault_excepcion_declarada — el guard cae con el dato que vino a medir (AP-61).**

`RecursionError` **no hereda de `yaml.YAMLError`**. El parser de PyYAML es recursivo y el frontmatter es dato externo, así que `x: [[[[[…` —doce caracteres de escribir— desborda la pila DENTRO de `safe_load`. Un `except yaml.YAMLError` alrededor de esa llamada parece contener el fallo y no lo contiene: la excepción sube entera y **una sola nota hostil tumba el barrido completo del vault**, no la lectura de esa nota.

## `recursos`

- **Comando:** `python scripts/vault_recursos.py --check --strict`
- **Mide:** Ningún consumidor cruza una frontera de contexto para leer un recurso que no necesita el fan-out del productor (AP-62).
- **Se arregla con:** partir el productor en catálogo y motor y repuntar a los consumidores al dueño; partir el fichero solo no mueve la cifra —lo enseñó v40.27—, y reclasificar el productor al núcleo sin medirle el fan-out lo vería AP-59
- **Normas:** [AP-62](../normas/AP-62/porque.md)

**vault_recursos — el consumidor paga el fan-out del productor (AP-62).**

v40.27 quitó veinte de los sesenta y dos cruces de contexto con un solo movimiento, y el hallazgo que lo permitió no se buscó: se tropezó con él. De los veinticuatro importadores de `vault_norms`, veintiuno solo querían una tabla constante; entraban por una fachada que reexporta el motor y sus once dependencias, y por el camino convertían **leer un recurso** en **cruzar una frontera de negocio**.

## `procesos_git`

- **Comando:** `python scripts/vault_procesos_git.py --check --strict`
- **Mide:** Ninguna tool ni módulo levanta git por su cuenta: el verbo lo juzga vault.kernel.procesos_git y un mutador solo existe si está autorizado con su motivo (AP-68).
- **Se arregla con:** mover la llamada al dueño —ejecutar_git(repo, [...])—; si de verdad hace falta un mutador nuevo, autorizarlo en MUTADORES_AUTORIZADOS con su motivo escrito, que es el diff que lo revisa. No hay baseline: un sitio fuera del dueño es deuda nueva por definición
- **Normas:** [AP-68](../normas/AP-68/porque.md)

**vault_procesos_git — el git del toolkit pasa por un dueño, y el dueño mira (AP-68).**

Auditoría del 2026-10-23 sobre la pregunta «¿ejecuta alguna tool git sin supervisión?». El veredicto fue que no —doce sitios de lectura, un único mutador acotado al bootstrap de `vault_init`, cero `shell=True`, cero `--force`— pero que **nadie lo verificaba**: la propiedad era verdad por inspección de una tarde, no por guard. Mañana un `git clean -fdx` en una tool entraría sin que ninguna puerta se pusoera roja.

## `produccion`

- **Comando:** `python scripts/vault_produccion.py --check --strict`
- **Mide:** Toda promesa hecha a quien instala esto —versión mínima, dependencia, plataforma, superficie de red— tiene a alguien que la ejerza, y los huecos están declarados con su motivo.
- **Se arregla con:** añadir el ejecutor que falta, o declarar la promesa como descubierta con el motivo escrito; las demás puertas miden el repo contra sí mismo y en esa sala no está el consumidor, que es como >=3.9 pasó en verde sin que ninguna máquina ejecutara 3.9

**vault_produccion — «¿puede usar esto otra persona, y con qué fiabilidad?»**

De una pregunta del usuario, hecha con v40.30 recién cerrada y las 20 puertas en verde: *«¿entonces ya puede ser usado por otras personas, aparte de mí, y con resultados óptimos, decentes y fiables?»*

## `esquemas`

- **Comando:** `python scripts/vault_esquema.py --check --strict`
- **Mide:** Los JSON Schema de schemas/ son los que el contrato de nota produce para cada versión, y ninguno se edita a mano.
- **Se arregla con:** python scripts/vault_esquema.py --sync; si el cambio es del contrato, va en vault_contrato_nota con su fuente en HISTORIA

**vault_esquema — publica el contrato de nota como un JSON Schema por versión.**

El contrato de campos de una nota vive en `vault_contrato_nota`, que es Python. Quien consume un vault sin este toolkit —un editor, una CI de otro lenguaje, un agente que solo sabe JSON Schema— no puede importarlo. Esta tool lo publica en `schemas/`, un fichero por versión mayor del estándar, junto con los de las versiones anteriores: un vault que se quedó en v28 se valida contra lo que v28 exigía, no contra lo de hoy.

## `metricas`

- **Comando:** `python scripts/vault_metricas.py --check --strict`
- **Mide:** Toda métrica de desarrollo y de producto declara qué mide, de dónde sale y su objetivo con plazo y dueño (o por qué no lo tiene), y el histórico de observaciones solo crece.
- **Se arregla con:** corregir la entrada de METRICAS; una observación borrada se restaura desde HEAD, y docs/METRICAS.md se regenera con python scripts/vault_metricas.py --doc

**vault_metricas — métricas de desarrollo y de producto con objetivo, dueño y tendencia.**

Hasta 2026-10-14 el repo medía su **deuda** —las baselines llevan objetivo, fecha, cadencia y dueño desde v40.24— pero no su **proceso** ni su **producto**. Cuánto tarda la suite, cuántos fallos destapa cada ronda, cuántas tools fallan el smoke, qué tal le va al agente del banco: esas cifras se ejecutaban, se leían en un log de `%TEMP%` y se perdían. Sin histórico no hay tendencia, y sin tendencia «va mejor» es una opinión.

## `doc_staleness`

- **Comando:** `python scripts/vault_doc_staleness.py --check --strict`
- **Mide:** Todos los artefactos derivados del vault (data-framework.json, norm-registry.json, quality-index.json, etc.) existen y contienen JSON válido.
- **Se arregla con:** Regenerar con: vault_fundamentals --framework && vault_norms --rebuild && vault_compact_contracts && vault_quality_check && vault_tags

**vault_doc_staleness — verifica que los artefactos derivados existen y son válidos.**

Comprueba que los JSON derivados de los catálogos Python existen, contienen JSON válido y no están huérfanos (existencia vs. contenido obsoleto).
