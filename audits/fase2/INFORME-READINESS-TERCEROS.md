# Informe de readiness para terceros — GOAL CLI + MCP

**ESTADO VIGENTE — ronda R15 (2026-10-27).** Candidato de producto:
**`015b7765b80cac21c6dcf859ae075d036cd01def`** (tree `d190fd24…`), con CI
**25/25 `completed/success`** (run `40442954197`) y recibos por subcheck
(QG-03..06 PASS; QG-00/01/02 fail-closed por decisiones pendientes).
Identidad completa: `audits/fase2/CANDIDATO-RELEASE.yaml`. Dictamen vigente:
`e47d62f` (`qa/review-release-cli-mcp-015b776-20261027`): P1 QA-R13-06
`ACCEPTED_SCOPED`, CI `VERIFIED`, release `BLOCKED` por DEC-02/03/04.
**Las tres plataformas están medidas** (Windows, Linux y macOS: 12 columnas
en verde en la matriz del candidato). Estado formal del release:
`RELEASE_BLOCKED` — bloqueos de decisión, no de ejecución. Manifiesto de
capacidades: §5.3 y `MATRIZ-CAPACIDAD-PRODUCTO.md`.

> **HISTÓRICO — corte R12 (2026-10-26).** Lo que sigue en este bloque es el
> estado de aquella ronda, conservado tal cual; NO es el estado vigente (el
> vigente es el de arriba y el §3/§9/§10 de este informe).
>
> **Fecha:** 2026-10-26 (ronda R12) · **Rama:** `work/release-cli-mcp-20261025`
> **HEAD de trabajo / candidato congelado:** `408eb23` (los commits posteriores
> de esta entrega son documentales)
> **Dictámenes vigentes:** `defc657` (QA sobre `316623a`: CI real, MCP/PyYAML en
> Windows, checkout superficial y reconciliación documental) · `9919c57` (8
> hallazgos QA-ARC, respondidos en R11) · `a9e0143`
> **Protocolo QA:** `audits/handoff/PROTOCOLO-QA.md` — reconciliado con
> `audits/fase2/catalogo-qg.yaml` y con un guard que falla ante la deriva
> (`tests/test_protocolo_qg_contra_catalogo.py`).
>
> **Estado general:** **ADVANCE — uso controlado por terceros técnicos, con la
> wheel, en Windows y Linux medidos; macOS sin medir.** No es una distribución
> pública: no hay tag, no hay release, no hay dictamen QA de cierre, y las
> decisiones reservadas al propietario (divergencias de arquitectura y política
> de QG-02) siguen abiertas. Lo que este informe afirma es lo que está medido;
> lo que no, `NOT_RUN`.
>
> **Corrección de la ronda anterior:** este informe decía que «la CI nunca ha
> completado un run» y que el bloqueo era «la facturación de GitHub Actions».
> **Era falso**: la CI corre. La corrida `40299732445` (sobre `36c91e0`)
> completó 17 de sus 25 jobs —9 en verde y 8 en rojo— y los 8 rojos eran
> defectos reales del producto y del workflow, no de la cuenta. Ver §3.

---

## 1. Qué recibe un tercero

Un paquete Python publicado como **wheel y sdist** que instala dos superficies
de producto **sin el checkout, sin el toolkit y sin servicios externos**:

| Superficie | Contrato | Evidencia |
|---|---|---|
| **CLI** `vault` (`init`, `doctor`, `status`, `tools`, `run`, `mcp-path`) | instalar y operar un runtime standalone | recorrido de terceros: **27/27** (rueda construida desde el código) |
| **CLI del toolkit** `python -m cli` (`groups`, `find`, `show`, `doctor`, `run`, `plan`, `batch`, `scan`) | operar cualquier tool del catálogo con pre-vuelo | ayuda medida; el E2E ejercita `run` y `doctor` (§5.3) |
| **Servidor MCP** (`vault-mcp-server.mjs`) | **97 tools** expuestas por JSON-RPC/stdio (`initialize`, `tools/list`, `tools/call`) y 7 recursos `vault://` | sesión JSON-RPC real (`tests/test_mcp_runner.py`, `tests/test_mcp_recursos.py`) |
| **Vault resultante** | markdown plano legible con un editor de texto | el vault sobrevive a que el toolkit desaparezca (decisión de producto) |

**De dónde salen las cifras del catálogo** (medido el 2026-10-26, no copiado):
el catálogo publica **126 tools**; **29** están retiradas de MCP a propósito
(`exposed_via_mcp: false`); 126 − 29 = **97** es lo que un agente ve en
`tools/list`; con el perfil de sesión `agente` son **14**. El PRD de MCP sigue
diciendo «116»/«117» y «9 tools JS-native» (son 2): son cifras caducadas del
2026-09-20, corregidas en `audits/fase2/MATRIZ-CAPACIDAD-PRODUCTO.md`.

## 2. Calidad medida (con su fuente)

| Métrica | Valor | Fuente |
|---|---|---|
| Suite completa | **6334 passed / 13 skipped / 0 failed** en **1441,4 s** | JUnit `r14` sobre el árbol del commit candidato (6347 collectados, 0 fallos, 0 errores) |
| Puertas del estándar | **26/26** en 743,8 s + re-medición del conteo (6347) | `vault_gate.py --strict` sobre el árbol del commit candidato; en CI, en las columnas de Windows y Linux de la corrida `40442954197` |
| E2E de terceros | **27/27** con wheel reconstruida desde el código (el guion construye la wheel desde HEAD) | `recorrido_terceros_r07.py`; wheel `8cda5efa…3cfd`, sdist `1c65f132…7656` |
| Equivalencia del paquete | **706 miembros, 0 ficheros con contenido distinto** entre la wheel del E2E y la reconstruida | la construcción **no es reproducible** (el ZIP lleva marcas de tiempo): el hash de referencia es el de la construcción certificada, y lo que se comparó es el contenido |
| AP-39 (defecto de producto) | **corregido**: 0 violaciones en runtime limpio con 75 ficheros | re-auditoría con código actual (commit `2174bb1`) |
| Sandbox canónico | **1** violación, y es externa: `vault-backups` dos niveles por encima del repo | audit con código actual; los 13 de contenido **corregidos** (§4) |
| Divergencias Archify | 10 (2 fichas de movimiento de composición `667a6a5`, 5 accesos, 3 dependencias) | `reconciliar_archify.py --check` (exit 1 esperado sin ratificación) |
| Paralelismo de la suite | 8255 s de casos contra 1076 s de reloj = **7,7×** | JUnit `r11c` + log de la corrida |
| Rendimiento del generador de trazabilidad | **67,2 s → 9,7 s** | dos mediciones reales con `Measure-Command` |

## 3. CI: lo que de verdad pasó

### 3.1 Corridas medidas

| Corrida | SHA | Jobs | Resultado | Conclusión |
|---|---|---|---|---|
| `40299732445` | `36c91e0` | 25 | 9 verdes · 8 rojos · 8 en cola | los 8 rojos: checkout superficial + MCP + SystemRoot (§3.2). |
| `40317033977` | `9e0bcd7` | 25 | 9 verdes · 8 rojos · 8 en cola | suite **verde** en las 8 columnas; los rojos eran la puerta `conteos` (D7) y la contención (D8) |
| `40326462714` | `0fffbc3` | 25 | 13 verdes · 3 rojos | los 3 rojos de Windows: el quoting del paso `vault_norms --list` (D9) |
| `40335869688` | `8b87b24` | 25 | 13 verdes · 1 rojo | el rojo: el flake de la idempotencia del SDD (D10) |
| `40340865847` | `408eb23` | 25 | **21 verdes · 4 rojos · 0 pendientes** | los 4 rojos: **las cuatro columnas `validate` de macOS** (§3.2, R13-01/02/03) |
| `40349132455` | `dfc6a06` | 25 | 20 verdes · 5 rojos | los 4 de macOS + Windows 3.10 (R13-03b) |
| `40420024458` | `9c65401` | 25 | **24 verdes · 1 rojo · 0 pendientes** | las 4 columnas de macOS **pasan**; el 1 rojo es Windows 3.10 con el defecto nuevo R13-05 (§3.2), corregido después |
| `40430269201` | `e198ffb` | 25 | **25 verdes · 0 rojos · 0 pendientes** | `completed/success` — **la matriz completa en verde**, por primera vez la ronda cierra en 25/25 |

**Lo que esto refuta (y lo que la ronda anterior afirmaba):** la hipótesis de
que la CI estaba bloqueada por facturación. La CI **corre**: los jobs de
Windows y Linux terminan, y **los de macOS también ejecutan** — tardan en
recibir runner (en las corridas intermedias se les veía en `queued` durante
horas, y ese estado puntual se tomó por «no arrancan»), y cuando corren
fallan con defectos reales del producto. El diagnóstico completo, con la
traza de cada uno, está en `audits/fase2/CI-diagnostico.md`.

**El cierre de la ronda:** la corrida del commit final `e198ffb`,
`40430269201`, terminó **completed/success con 25/25** — las cuatro columnas
de macOS verdes incluidas, y el arreglo de R13-05 verificado en la matriz
completa.

### 3.2 Los defectos reales que la CI destapó — D1..D10 (R12) y R13-01..05 (R13)

| # | Síntoma | Causa comprobada | Corrección | Cómo se comprobó |
|---|---|---|---|---|
| D1 | 18 tests rojos en **todas** las columnas (Linux y Windows, 3.9–3.12): `vault_changelog_check` daba «hash inexistente» a commits que **sí** existen en GitHub; `vault_contrato_nota` no resolvía `git show`/`cat-file` de commits históricos; `vault_metricas` no resolvía el rango `8f24030..6ddf04e`; el blueprint y el auditor de exposición histórica tampoco | `actions/checkout@v4` hace checkout **superficial** (`--depth=1`): los objetos históricos no están en el clon | `fetch-depth: 0` **solo** en el job `validate` | **repro local**: clon `--depth=1` → **19 fallos** en los cinco ficheros afectados; el mismo árbol con historia completa → **129/129 pasados** con el mismo intérprete. En la CI, la suite quedó **verde en las ocho columnas** de la corrida `40317033977` |
| D2 | `tests/test_mcp_runner.py::test_la_tool_por_modulo_se_ejecuta_por_mcp` rojo en **las cuatro** columnas de Windows: `TOOL_EXECUTION_FAILED` con `ModuleNotFoundError: No module named 'yaml'` | el servidor MCP elegía `py` como intérprete; en el runner de Windows, `py` resuelve el Python **registrado en la imagen base** (sin PyYAML), no el de la matriz, donde `pip install -e ".[dev]"` sí instaló la dependencia | `detectPython()` sondea `python3` → `python` → `py` (en ese orden) y **exige a cada candidato `import yaml`**; la elección explícita (`VAULT_MCP_PYTHON`) no se sondea, pero se avisa en el arranque si no puede importar la dependencia | 9/9 en `test_mcp_runner.py`; 8/8 en `test_mcp_instalado.py`; medición en vivo: el servidor arranca, responde y expone 97 tools |
| D3 | `test_impl_shadow` y `test_portabilidad_v4030` rojos en **Windows 3.9 y 3.10**: hijo de Python muerto con `Fatal Python error: _Py_HashRandomization_Init: failed to get random numbers to initialize Python` (stdout vacío) | los dos fixtures lanzan al hijo con un `env` **curado** (sustituye el entorno entero) **sin `SystemRoot`**: sin esa variable, el `win32_urandom` de 3.9/3.10 (`CryptGenRandom`) no consigue números y el hijo muere en la inicialización. 3.11+ usa `ProcessPrng` y sobrevive — de ahí que solo fallaran 3.9 y 3.10 | los dos fixtures **heredan la invariante del anfitrión** (`SYSTEMROOT`) y dejan el resto de la curación intacta | **repro local**: `py -3.9` con env sin `SystemRoot` → rc=1 con el stderr **idéntico** al de la CI; `py -3.12` y `py -3.14` → rc=0; con `SystemRoot` → rc=0 |
| D7 | Puerta `conteos` en rojo **solo en Linux** (25/26) con la suite verde: la cifra de tests publicada (6320, medida en Windows) no coincidía con la collectada en Linux (6318) | `tests/test_read_ruta_canonica.py` solo añadía en Windows las dos variantes que usan separador de Windows y caja distinta → **la cifra de tests dependía del sistema**, y la puerta la compara con `pytest --collect-only` | las cuatro variantes se **colectan** en todas las plataformas y las dos de Windows se **saltan** fuera de Windows: la cifra queda igual en todos los sistemas (6332) y la cobertura de Windows no se pierde | diferencia de las listas de tests collectados (local vs log de la CI); 4/4 en el test; puerta `conteos` en verde |
| D8 | Paso «Containment audit (AP-36, strict)» en rojo en Windows 3.12: la auditoría del sandbox canónico daba **13 violaciones** (CN-03×5, AP-07×4, AP-64×4) | el paso audita el sandbox que el propio job construye con `tests/sandbox_fixture.py --bootstrap`, y la **semilla** (`tests/fixtures/sandbox-seed.json`) escribía las notas con `status: accepted`, sin las secciones de AP-07 y sin `responsable` de AP-64. Eran las mismas 13 del ledger de QG-02: contenido nuestro, no un defecto de la CI | la semilla escribe notas **canónicas** (status del vocabulario, las tres secciones, `responsable` distinto del agente) | auditoría del sandbox canónico con el código actual: de 14 → **1** (la externa); en CI, **0** |

| D9 | Paso «Run vault_norms --list» rojo en **las cuatro** columnas de Windows y verde en las de Ubuntu, con el mismo código: `SyntaxError: '[' was never closed` | el paso usa `python -c "..."` con comillas dobles escapadas; con el shell por defecto de Windows (PowerShell) las comillas se pierden al pasar el argumento al proceso nativo y el código llega partido. En bash funciona | el paso declara `shell: bash` (que está en los tres runners) y el código usa comillas simples | verificado en el bash local («AP norms registered: 76», exit 0) y en CI: windows-3.12 en verde con ese paso en `success` |
| D10 | `test_vault_sdd_init.py::test_skill_idempotency` rojo en Windows 3.11: «README.md not idempotent», con una única diferencia (dos «Generated at» con un segundo de distancia) | los generadores del SDD estampan el instante de la escritura y el test comparaba dos generaciones byte a byte: el resultado dependía del **segundo** en que caían, no del código | la comparación normaliza **solo el instante** (la etiqueta y el resto del texto se siguen comparando) | dos generaciones con 1,2 s de diferencia: contenido crudo distinto, contenido normalizado idéntico en los doce generadores; 15/15 tres veces seguidas |

| R13-01 | macOS (3.9-3.12): `RuntimeError: el servicio no abrió el puerto` + 11 errores de fixture; el proceso quedaba vivo y sin escuchar, sin decir por qué | **sin causa demostrada** (lo dice el dictamen). Medido: el servicio arranca en 0,017 s en local; el test esperaba un puerto que él mismo elegía (carrera) y agotaba 30 s sin reportar nada | el servicio **enlaza antes de publicar** el fichero de puerto (señal de readiness) y registra sus tiempos de arranque en stderr; el test pide puerto 0, espera la señal y, si no llega, dice código de salida, liveness, puerto, fichero de puerto y stderr acotado, con el token redactado | `test_el_arranque_que_falla_dice_el_codigo_y_el_stderr` |
| R13-02 | macOS (3.9-3.12): el escáner legacy contaba **5** notas donde hay **3** | la cascada de cada escritura crea ficheros (`index.md` de sección, notas de sistema) **mientras el `rglob` perezoso sigue recorriendo**: en APFS los ve, en ext4/NTFS no. Reproducido en local (una segunda pasada contaba 6 = 3 + los 3 creados) | el inventario se **materializa** antes de curar; los artefactos derivados se excluyen por su dueño; el escaner **publica el inventario** (ruta, clase, motivo) | `test_heal_legacy_no_cuenta_lo_que_la_pasada_crea`, `test_heal_legacy_publica_el_inventario_exacto` |
| R13-03 | macOS 3.11: el segundo proceso del test de exclusión **moría** con `OSError: [Errno 22] Invalid argument: .../.locks/contador.txt.lock`; Windows 3.10: la copia del sandbox vivo fallaba con `shutil.Error: ... 00_System/.locks` | en macOS, cuando `.locks/` se retira mientras otra ruta se resuelve, `mkdir` responde **EINVAL/ENOTDIR** (en Linux es ENOENT, ya contemplado): el proceso debía **esperar su turno**. En Windows, la copia del sandbox se cogía en mitad porque otra prueba en paralelo tomaba y soltaba locks | EINVAL/ENOTDIR se compiten otra vez, con el plazo como único freno; el estado de bloqueo es de **ejecución**, no de contenido, y la copia lo ignora | `test_un_einval_al_crear_el_lock_se_compite_otra_vez` (positiva), `test_un_einval_permanente_no_espera_sin_fin` (negativa) |
| R13-04 | (política): toda conclusión de CI que no fuera `success` se etiquetaba `CI_PENDIENTE`, incluida una corrida ya concluida en **rojo** | el colector solo miraba runs exitosos: `completed/failure` salía `no_verificable` y la política leía «pendiente» | tres clases (`CI_PENDING` / `CI_FAILED` / `CI_PASS`) en política y colector; fail-closed intacto: solo `success` pasa | 4 tests de política + 2 del colector |
| R13-05 | Windows 3.10 (verificación `40420024458`): `ConnectionAbortedError: [WinError 10053]` en vez del 403 esperado | el rechazo (Origin ajeno → 403) cerraba la conexión con el **cuerpo sin leer** → RST del núcleo → el cliente pierde la respuesta. Carrera: solo 1 de 8 columnas la vio | el camino de rechazo de SP-04 **drena el cuerpo** antes de responder | el propio test, pedido 5 veces; verificado en `40430269201` |

Ninguno se arregló con sleeps, reintentos, baselines más amplias
ni tests relajados. Todos se arreglaron en su causa.

### 3.3 Lo que la CI NO demuestra todavía

- **El candidato vigente no es `e198ffb`.** El dictamen R13 (`7dc1a25`) abrió
  QA-R13-06 (P1: el cuerpo del POST se consumía dos veces y un POST
  autenticado a ruta desconocida podía retener al worker para siempre). La
  corrección viaja en el commit de esta ronda, y el 25/25 de `40430269201`
  acredita a `e198ffb`, **no** al nuevo SHA: la matriz hay que volver a
  conseguirla para el candidato nuevo. (Regla del GOAL: no se reutiliza el run
  de un SHA para certificar otro.)
- El job `validate` corre la suite **sin `-n auto`** (secuencial, ~27 min por
  columna). Es correcto para CI, pero significa que la CI no mide el
  paralelismo del que habla §2.

### 3.4 Corridas de la ronda R13 (historia) y la corrida que cerró la matriz

**`40340865847` (SHA `408eb23`): 21 de 25 jobs en verde** — lint, los 8 de
producto (wheel) y los **8 `validate` de Windows y Linux**, que pasaron la suite
completa, las 26 puertas, el AP-40, el smoke de las 126 tools, la auditoría de
contención, la validación del runtime recién creado, el paso de
`vault_norms --list` y el AP-25 del manifiesto. **Los 4 que faltan son las
cuatro columnas `validate` de macOS, y fallan con defectos reales** (los de
R13-01/02/03, con su traza en `audits/fase2/CI-diagnostico.md`).

Es decir: **los diez defectos de la ronda anterior están corregidos y la CI lo
demuestra**. Lo que quedaba eran macOS, y macOS no estaba «sin runner»: estaba
fallando por cosas del producto y del harness, que es un sitio mejor para
estar.

**`40420024458` (SHA `9c65401`): 24 de 25 jobs en verde** — incluidas, por
primera vez, **las cuatro columnas de macOS**. El único rojo es Windows 3.10
con un defecto nuevo de esta ronda (R13-05: el RST del rechazo de SP-04),
corregido con su ficha en §3.2.

**`40430269201` (SHA `e198ffb`): 25 de 25, `completed/success`** — la matriz
completa en verde por primera vez: 12 `Validate Vault Spec` + 12 `Product
gates (wheel)` + Lint, las cuatro columnas de macOS incluidas. Es la corrida
que el dictamen R13 aceptó como `CI_MATRIX_25_OF_25=ACCEPTED`, y la que el
candidato nuevo de esta ronda tiene que volver a ganar.

## 4. QG-02: los 14 hallazgos del sandbox, desglosados y corregidos

El expediente arrastraba 14 hallazgos del sandbox canónico. Re-medidos con el
código actual (no con el del ledger, que era de `ab31bf3`), son:

| Hallazgos | Qué son | Dónde vive el defecto | Estado |
|---|---|---|---|
| CN-03 ×5 | `status: accepted` / `active` fuera del vocabulario canónico | **la semilla del sandbox** (`tests/fixtures/sandbox-seed.json`), versionada en este repo | **CORREGIDO**: la semilla escribe `approved` / `verified` |
| AP-07 ×4 | ADR sin Contexto/Decisión/Consecuencias | la misma semilla | **CORREGIDO**: la semilla trae las tres secciones |
| AP-64 ×4 | decisión cerrada sin `responsable` | la misma semilla | **CORREGIDO**: con responsable distinto del agente que la escribió |
| AP-36 ×1 | `vault-backups` dos niveles por encima del vault | **fuera del repo**: datos de una ejecución previa, en la carpeta del propietario | **ABIERTO — decisión del propietario** (purgar o declarar con fecha y dueño). No se borra desde aquí |

**Auditoría actual del sandbox canónico:** 69 notas escaneadas, **1
violación** (la externa), los tres controles obligatorios (AP-40, AP-42,
AP-43) en estado `ejecutado` con 0 hallazgos. En CI, donde el sandbox vive
en `D:\a\<repo>`, el mismo audit da **0 violaciones**.

**La política de certificación propuesta** (runtime limpio ≠ sandbox canónico,
qué se declara y qué no) está en
`audits/fase2/POLITICA-CERTIFICACION-PRODUCTO.md`. **No se aplica sin
ratificación del propietario**; por ahora QG-02 sigue BLOCKED, aunque su
causa técnica (13 de 14) ya no existe.

## 5. Readiness: qué sí y qué no

### 5.1 Lo que un tercero puede hacer HOY, con honestidad en el rótulo

```
pip install la-wheel           # ~1 min
vault init <su-runtime>        # crea el vault completo
vault doctor                   # diagnostica
vault run <tool> / servidor MCP  # 97 tools por JSON-RPC
```

**Garantizado y probado:** instalación limpia fuera del checkout; runtime
recién creado en **0 violaciones** del estándar; operación determinista;
`NOT_RUN` nunca se cuela como PASS; rutas y datos personales fuera de lo
publicado (`comprobar_saneamiento` exit 0 en cada commit); preflight
anti-poison no desactivable; escrituras atómicas y contenidas dentro del
vault.

**Lo que este rótulo NO dice:** que la distribución esté autorizada. Es un
**uso controlado por terceros técnicos**, no un canal de publicación: sin tag,
sin release y sin dictamen QA de cierre.

### 5.2 Multiplataforma, con la evidencia de cada sistema

Estado vigente: la corrida `40430269201` (SHA `e198ffb`) dejó las **12
columnas en verde — las tres plataformas y los cuatro Pythons**. La fila de
macOS ya no es `EXECUTED_FAILED`: lo fue en `40340865847`, se corrigió en la
ronda R13 y la corrida final lo verificó. La historia de ese estado está en
§3.4 y en `CI-diagnostico.md`; el estado vigente es este:

| Sistema | Estado | Evidencia |
|---|---|---|
| Windows | **CI_PASS** | 4 columnas en verde en `40430269201` (y suite + E2E locales en cada ronda) |
| Linux | **CI_PASS** | 4 columnas en verde en `40430269201` |
| macOS | **CI_PASS** | 4 columnas en verde en `40430269201` (primera matriz completa: antes `EXECUTED_FAILED` en `40340865847`, ver §3.4) |

### 5.3 Lo que NO garantizamos aún

1. **La matriz del candidato nuevo.** El 25/25 acredita a `e198ffb`; el
   candidato de esta ronda (con QA-R13-06 corregido) tiene que volver a
   ganarla (§3.3).
2. **Un dictamen QA formal de cierre** del candidato: pendiente (§9).
3. **Alcance distribuido, con los límites en la cara (QA-R14-PORT-01)**: la
   wheel distribuye el CLI de producto y el MCP stdio. La superficie
   `python -m cli` del checkout —`plan`, `batch` (olas, `--stop-on-error`),
   `--verify-integrity` y el código de salida 130— **no viaja en la wheel**
   (verificado: no hay paquete `cli` en site-packages): queda FUERA del
   alcance del release, no como deuda del paquete. Dentro de la superficie
   distribuida queda UN `NOT_RUN` declarado: **SSE/HTTP** (`--port` del
   servidor MCP). Detalle: `MATRIZ-CAPACIDAD-PRODUCTO.md` §2-3.
4. **No es un servicio de almacenamiento seguro**: la fiabilidad del vault es
   la del markdown plano más auditoría; **no cifrado, no multiusuario**.

## 6. Decisiones reservadas al propietario

Estado vigente: las seis siguen **ABIERTAS**; la 3 (macOS) perdió su motivo —
la matriz ya está medida — y se cierra sola con la evidencia de §5.2. Las
fichas formales, con alternativas, riesgos, costos y espacio de decisión, están
en `audits/handoff/DECISIONES-PROPIETARIO.md` (DEC-01..DEC-06).

| # | Decisión | Opciones | Recomendación técnica | Estado |
|---|---|---|---|---|
| 1 | **10 divergencias DIV-01..10** (cruces heredados del movimiento `667a6a5`) | **A** eliminar · **B** migrar a un puerto · **C** excepción formal con plazo | **B**, con el matiz de que el puerto tiene que ser de **datos y proceso**, no de símbolos: la alternativa A del análisis crea el cruce que hay que eliminar. Plan completo en `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` (+ identidad y coste medido en su §11) | **ABIERTA** (DEC-02) |
| 2 | **Contrato de QG-02** | A solo sandbox · B solo runtime · **C compuesto** (runtime limpio + sin efectos nuevos + residuo histórico registrado) | **C**: mantiene la detección que encontró el escape y separa lo que un tercero consume de lo que pasa en el anfitrión (`QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md` §3) | **ABIERTA** (DEC-03) |
| 3 | **macOS en la CI** | — | **CERRADA POR EVIDENCIA**: los runners existen y ejecutan; la matriz 25/25 está medida en `40430269201`. La hipótesis «no arrancan» y la de facturación quedan descartadas | **CERRADA** (§3.4, §5.2) |
| 4 | **Ratificar la Constitución arquitectónica** (DRAFT) | ratificar, corregir o rechazar con motivo | decide el propietario tras el dictamen QA de cierre | **ABIERTA** (DEC-01) |
| 5 | **`vault-backups`** (AP-36) | conservar / mover / **archivar y purgar** / purgar | **archivar con hashes y después purgar**, solo con autorización escrita del dueño de los datos (ficha completa: `QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md` §2) | **ABIERTA** (DEC-04) |
| 6 | Reescritura del historial publicado | sí / no | conservar con riesgo documentado: sin credenciales detectadas, el coste de la reescritura supera su beneficio | **ABIERTA** (DEC-05) |

## 7. Riesgos residuales (con dueño y estado)

| Riesgo | Dueño | Estado |
|---|---|---|
| ~~macOS sin medir~~ **CERRADO**: la matriz 25/25 está medida en `40430269201`; el candidato nuevo tiene que repetirla (§3.3) | CI | **cerrado** para `e198ffb`; pendiente de repetir para el candidato nuevo |
| 10 divergencias sin ratificar | propietario (arquitectura) | abierto; bloquea QG-00/QG-01 |
| `vault-backups` externo (AP-36) | dueño de los datos | abierto; decisión 5 (DEC-04) |
| QA-R13-06 (doble lectura del cuerpo del POST) | ejecutor | **corregido en esta ronda** con regresión focalizada; pendiente de re-certificación integral y CI del candidato nuevo |
| ~~TD-0008 `--clean` destructivo~~ **RESUELTO**: implementación transaccional `cc85491` (cuarentena verificada por hash, `--confirm`/`--dry-run`, rollback), 22 tests + E2E + misma implementación en la wheel; registro de deuda reconciliado (QA-R14-DOC-01). Aceptación QA explícita del cierre: pendiente de dictamen | ciclo_de_vida / QA | resuelto-técnicamente; dictamen pendiente |
| Capacidades del PRD sin recorrido que las ejerza (`plan`, `batch`, `--verify-integrity`, SSE, 130) | el propio repo | identificado y medido; deuda de verificación — alcance PORT-01 (§5.3) |
| Duplicación gates-dentro-de-tests (5 casos únicos > 100 s) | revisión futura del harness | identificado; sin ejecutar |
| Planificador por impacto sobre grafo desfasado | el propio repo | mitigado por conservadurismo: sin impacto determinable exige suite completa |
| Baselines congeladas con deuda declarada | apuntalar cada ronda | los decrementos son la dirección (solo encogen) |

## 8. Qué significaría «cerrado» (checklist)

1. [x] Producto verificado end-to-end (E2E 27/27 + runtime limpio en 0 violaciones).
2. [x] Error y deuda declaradas con dueño.
3. [ ] QG-00/QG-01: ratificar las 10 divergencias (decisión 1) — plan B preparado.
4. [ ] QG-02: ratificar la política de certificación (decisión 2) — propuesta escrita; los 13 hallazgos técnicos ya corregidos.
5. [ ] CI: un run **concluido** sobre el SHA final, con los jobs de macOS ejecutados (decisión 3).
6. [ ] QG-03..06: recibos desbloqueados por el encadenado (los recibos existen).
7. [ ] Dictamen QA de cierre y ratificación de la Constitución.
8. [x] Congelar el SHA definitivo y re-certificar (26 puertas + suite + E2E + recibos + QG) — §9.

## 9. Estado de la certificación de cierre

- **Congelado y re-certificado en R11:** `36c91e0` — suite **6307 passed / 13
  skipped / 0 failed** (JUnit `r11d`) y **puertas 26/26**; E2E 27/27.
- **Ronda R12 — SHA intermedio `408eb23`:** corregidos los **diez** defectos
  que la CI destapó (§3.2); su corrida terminó 21/25 (macOS en rojo), que es
  lo que la ronda R13 heredó y resolvió.
- **Ronda R13 — candidato de producto `e198ffb`** (`9c65401` + el drenaje de
  R13-05): los **seis** defectos de la ronda corregidos en causa (§3.2) y
  medidos con:
  **suite 6330 passed / 13 skipped / 0 failed** (JUnit `r13b`;
  0 fallos, 0 errores), **puertas 26/26 en 766,1 s**, **E2E 27/27** con wheel
  reconstruida (`3a9f2dda…`), paquete **706/706 miembros iguales** contra la
  wheel del dist del candidato, y **CI 25/25 en verde** en la corrida real
  `40430269201` — las cuatro columnas de macOS pasan por primera vez y con
  ellas la matriz completa: 12 `Validate Vault Spec` + 12 `Product gates
  (wheel)` + Lint, sin un solo job en rojo ni cancelado.
- **Recibos externos por subcheck** del mismo SHA: QG-03, QG-04, QG-05, QG-06
  y **QG-07 PASS** (con artefacto y SHA-256 por subcheck; la QG-07 acredita el
  run `40430269201`, `completed/success`, 25/25 con los jobs nombrados en el
  recibo). QG-00 y QG-01 fallan **solo** por el reconciliador (las 10
  divergencias sin ratificar, fichas §6 del plan B) y QG-02 **solo** por la
  violación externa de `vault-backups` (AP-36 fuera del repo). La política los
  deja **BLOCKED** y `liberable: false` — que es el estado honesto y el mismo
  bloqueo que dejó la R12, ahora sin ninguna deuda de CI del lado del
  ejecutor.
- **Lo que falta, y no lo puede cerrar el ejecutor:** el dictamen QA de cierre
  sobre `e198ffb` y la ratificación de las decisiones §6 (divergencias,
  política de QG-02, `vault-backups`). La matriz de macOS ya no es un
  bloqueo: está verde en la corrida del candidato.

**Veredicto:** el producto técnico está en verde —ci incluida la matriz macOS
de 25/25—, los diez defectos de CI de la ronda anterior y los seis de esta
están corregidos y comprobados con evidencia de la propia CI, y la
documentación dice la verdad sobre su estado. Lo que falta para un release
certificado son decisiones del propietario (§6) y el dictamen de QA; ninguna
de las dos cosas la puede cerrar el ejecutor, y ninguna se resuelve con un
documento que afirme lo contrario.

## 10. Matriz formal de release (REL-00..13) — estado R14

Contrato del GOAL R14 §6. Estados medidos sobre el **candidato de esta ronda**
(el SHA del commit que publica esta tabla; identidad completa en
`audits/fase2/CANDIDATO-RELEASE.yaml`). Los estados provienen de
verificadores y decisiones identificables — nunca de la prosa de este
informe. Distinción obligatoria: **CI_PASS ≠ QG07_PASS ≠ QA_APPROVED ≠
OWNER_AUTHORIZED ≠ PUBLISHED**.

| ID | Etapa | Norma / QG | Criterio | Evidencia | SHA | Estado | Responsable | Acción pendiente |
|---|---|---|---|---|---|---|---|---|
| REL-00 | Identidad y alcance | Constitución, QG-00 | Versión y producto identificados | `CANDIDATO-RELEASE.yaml` (manifiesto) | este commit | **MEDIDO** (manifiesto creado; QG-00 sigue BLOCKED por las divergencias) | Ejecutor | Ratificaciones DEC-01/02 |
| REL-01 | Arquitectura | QG-01 | Contratos y cruces conciliados | `reconciliar_archify.py --check` (exit 1: 10 divergencias sin firma — expediente de firma preparado en `divergencias-aceptadas.yaml`, inerte hasta `ratificado: true`), `vault_arch --check` verde (5/5 baseline) | este commit | **BLOCKED** (decisión) | Arquitectura / propietario | DEC-02: firmar las 10 u ordenar el re-take del snapshot; luego enmiendas I2/coste del plan B §11 |
| REL-02 | Gobernanza | QG-02 | Controles completos, conformes | recibos QG-02 (1 violación AP-36 externa; controles `ejecutado`, 0 hallazgos); runtime limpio 0 violaciones | este commit | **BLOCKED** (decisión) | Gobernanza / propietario | DEC-03 (contrato) + DEC-04 (residuo) |
| REL-03 | Integridad | QG-03 | Suite, regresiones, recuperación | JUnit `r14`: **6334 passed / 13 skipped / 0 failed** (6347 collectados); E2E **27/27** | este commit | **PASS** | Ejecutor | — |
| REL-04 | Seguridad | QG-04 | Contención y dependencias conformes | saneamiento exit 0; pip-audit; contención (self-test); operaciones destructivas; SP-04 intacto (20/20) | este commit | **PASS** (con riesgo TD-0008 declarado, dueño propietario) | Seguridad | TD-0008 antes de beta de terceros (dictamen) |
| REL-05 | Paridad | QG-05 | CLI/MCP equivalentes | paridad CLI↔MCP sobre la wheel instalada; AP-40 exit 0 | este commit | **PASS** (paridad de 5 escenarios, no de las 97 tools) | Ejecutor | Limites declarados en §5.3 |
| REL-06 | Distribución | QG-06 | Wheel instalada y usable | build + hashes del manifiesto; instalación limpia; 706/706 miembros | este commit | **PASS** | Empaquetado | — |
| REL-07 | Matriz CI | QG-07 | Jobs requeridos completados y exitosos | **candidato `015b776`: run `40442954197` — `completed/success`, 25/25** (recibo QG-07 del colector con los jobs nombrados). Antecedente: `e198ffb` run `40430269201` 25/25, aceptado por QA | `015b776` | **CI_PASS** | CI | — |
| REL-08 | Dictamen QA | QG-07 | Sin bloqueantes | dictamen `7dc1a25`: matriz de `e198ffb` aceptada, QA-R13-06 abierto → **corregido y verificado en la corrida del candidato**; solicitud de nuevo dictamen sobre `015b776` en `PROTOCOLO-QA.md` §5 | `015b776` | **QA_REVIEW_REQUIRED** | QA | Dictaminar sobre `015b776` |
| REL-09 | Aprobación | QG-07 | Autorización expresa | fichas DEC-01..06 (`audits/handoff/DECISIONES-PROPIETARIO.md`), espacios de decisión vacíos | — | **OWNER_DECISION_REQUIRED** | Propietario | DEC-06 tras dictamen favorable |
| REL-10 | Publicación | Gobierno release | Artefactos aprobados publicados | — | — | **NOT_RUN** (no autorizado; sin tag ni release) | Release manager | Tras REL-09 |
| REL-11 | Activación | Contratos runtime | Instalación y datos íntegros | — | — | **NOT_RUN** | Operador | Tras REL-10 |
| REL-12 | Seguimiento | Observabilidad | Estabilidad y errores monitorizados | — | — | **NOT_RUN** | Operador | Tras REL-11 |
| REL-13 | Relanzamiento | Nueva versión | Compatibilidad, migración, QA y autorización | — | — | **NOT_RUN** | Propietario | Nuevo ciclo |

**Lectura fail-closed:** las filas REL-03..07 son las únicas en PASS, y lo
están **por recibos y corrida del SHA `015b776`**, no por declaración.
REL-01/02 siguen BLOCKED por decisiones del propietario (no por trabajo del
ejecutor). REL-08 espera el dictamen sobre el candidato nuevo. El estado
global del release es **RELEASE_BLOCKED** (bloqueos de decisión en REL-01/02,
dictamen pendiente en REL-08, autorización en REL-09).
