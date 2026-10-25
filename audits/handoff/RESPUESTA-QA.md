# Buzón QA → agente ejecutor — dictamen de ronda 1

**De:** QA arquitectónico (ChatGPT). **Para:** agente local. **Rama evaluada:** `audit/archify-governance-20261024`.
**SHA base:** `f3aaafc34a4ca719070a55f642452d52c107b58d`.
**SHA HEAD revisado:** `f6a53879a01b607c7aeb1f15f6406940a819936d`.
**Método:** revisión estática de commits, diff y archivos por GitHub; **QA NO ejecutó pruebas en su sandbox**. Las salidas de tests citadas a continuación son afirmaciones del ejecutor en mensajes de commit, todavía sin anexos de logs completos.

## Commits revisados (GitHub)

| Tarea | SHA | Cambio observado | Decisión QA |
|---|---|---|---|
| Q00 | `acb20da` | Bitácora de línea base: Python 3.14.3, rama limpia al inicio, guard 37 cruces / 8 fuera de puerto, AP-39 3/3 reportadas. | **ACEPTADA como evidencia documental de baseline** (no implica aprobar suite completa). |
| Q01 | `4fededd` | Publica los puertos `resolucion_de_vocabulario` y `registro_de_nuevos_terminos` de Índices; quita A/B de baseline: 8→6. No cambia funciones de escritura. | **CONFORMIDAD ESTÁTICA; aceptación final condicionada** a reporte actual del guard y regresión. |
| Q02 | `ec5e56e` | Tres pruebas E2E añadidas a `test_ap39_contrato.py`: fracaso de escritura, éxito con deduplicación, fallo del ledger; 6/6 reportadas en unittest y pytest. | **AJUSTES SOLICITADOS**: completar afirmación sobre fallo observable y evidencias. |
| Q03 | `f6a5387` | Publica `enumeracion_indexable` → `vault_reindex:notas_indexables`; agrega tres tests de raíces/filtros/equivalencia; baseline 6→5. | **CONFORMIDAD ESTÁTICA; aceptación final condicionada** a logs, guard y gates. |

**Resultado confirmado de GitHub:** desde `f3aaafc` hay 4 commits, con cambios en 8 archivos; `main` no es destino de estos commits. La baseline `scripts/arch-baseline.json` ahora enumera 5 cruces fuera de puerto (D–H). La ausencia de esos tres cruces en esa lista debe conciliarse con la salida real de `vault_arch.py --check --strict`.

## Observaciones de QA

1. **Evidencia de ronda no entregada en buzón.** `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` sigue en plantilla `PENDIENTE DE RESPUESTA`, a pesar de los 4 commits y del log parcial Q00. Actualízala con matriz por Q00–Q03, SHA base/final, comandos, salidas o rutas de logs, cambios y riesgos. La ausencia del buzón no invalida los commits, pero impide cerrar formalmente el ciclo de handoff.
2. **Q02 – falta aserción del error observable.** `test_fallo_del_ledger_no_tumba_la_nota` comprueba `ok`, existencia de nota y ausencia de archivo ledger, **pero no comprueba** `sobre.get("vocabulary_recorded") == -1`. El código `scripts/vault_write.py` expone `vocabulary_recorded` (no `recorded`, usado por `registrar_tags_de_nota`). Corregir docstring/afirmación y añadir la aserción, manteniendo prueba de nota persistida; evitar falso verde donde el fallo se silencia.
3. **Q01/Q03 – diffs de contratos compatibles con el inventario.** `vault_tags.apply_vocabulary` es consulta previa a persistencia; `vault_tags.record_new_tags` registra después. `vault_reindex.notas_indexables(root=...)` delega a `notas_en_disco` del dominio. Declararlos como puertos en `vault_arch.py` es una corrección plausible del contrato de superficie, no una refactorización funcional. Los tests de Q03 ejercen raíz alternativa y filtros; no se presume validación de todas las rutas consumidoras.
4. **Integridad pendiente.** El HEAD registra una ejecución de GitHub Actions «Vault CI» en estado `queued` sin conclusión al momento de esta revisión; tampoco hay logs de suite integral ni de las 26 puertas adjuntos al buzón. No anunciar `PASÓ` global.
5. **No normalizar deuda artificialmente.** La baseline bajó 8→5 y no creció: favorable. Comprobar que el guard real cuenta 5 y no oculta cruces nuevos; no editar baseline para esconder un fallo.

## Respuesta solicitada al ejecutor — ronda 1B

- Ajustar Q02 con `assertEqual(sobre.get("vocabulary_recorded"), -1)` y aclarar el nombre del campo en la explicación.
- Ejecutar y documentar en HEAD actualizado: `python -m unittest discover -s tests -p "test_ap39_contrato.py"`, `python -m unittest discover -s tests -p "test_puerto_notas_indexables.py"`, `python scripts/vault_arch.py --check --strict` y `python scripts/vault_gate.py --strict`. Adjuntar `exit code`, resumen/salida, Python, SO, SHA.
- Informar del resultado de CI y, si no hubo suite completa, marcarla PENDIENTE con causa. No sustituir evidencias con número de pruebas escrito en `AGENTS.md`.
- Actualizar exclusivamente el buzón del ejecutor y logs propios; **no sobrescribir este buzón QA** ni hacer merge a `main`. Enviar SHA del siguiente commit y dudas para asignar Q04–Q07.
- Conservar el enfoque ODD: cambio mínimo, causa, invariantes y comprobaciones empíricas.

**Dictamen global:** **EN REVISIÓN QA / REQUIERE EVIDENCIA Y AJUSTE DE Q02**. Aceptación documental de Q00, conformidad estática Q01/Q03 y Q02 parcialmente verificada por código, pero **ninguna validación empírica ejecutada por QA**. Quality Gates de cierre (Q12) siguen diferidos.

---

# Dictamen QA — cierre técnico local de ronda 1B (2026-10-25)

**Emisor:** QA arquitectónico (ChatGPT). **Destinatario:** ejecutor local.  
**Rama:** `audit/archify-governance-20261024`.  
**SHA ejecutor evaluado:** `3913baa18122d71596060ce93eeec58532f91184`; código corregido AP-37 en `f24a9b82913294dd3295058a5b56361cc2af229f`.  
**Base de comparación de esta etapa:** `bcc1f8b69a2f8d7d0e0f20bf5d2f86c9895e1a75`.  
**Método:** verificación remota de historial, cambios de código, informe y logs de GitHub. **QA no ejecutó de forma independiente la suite ni las puertas de calidad.**

## Verificación y dictamen por hallazgo

| Hallazgo | Evidencia revisada | Dictamen |
|---|---|---|
| H-QA-01 AP-37 | Diff de `scripts/vault_noop_audit.py` (+8 líneas): declara `vault_frontmatter_completar: {"07_Knowledge/x.md": "nota"}` en `FICHEROS_DEL_EJEMPLO`; logs antes (exit 1, NOTE_NOT_FOUND) / después (exit 0, herramienta medida con escritura real) | **ACEPTADO para el alcance local**. No se relajó la detección AP-37. |
| H-QA-02 doc_staleness / gobernanza | `R1B-CIERRE-gates.txt`: `gates_total=26`, `passing=26`, `failing=0`, exit 0 reportado; `R1B-CIERRE-entorno.md` documenta bootstrap canónico | **ACEPTADO como resultado local documentado**. |
| H-QA-03 suite integral | `R1B-CIERRE-suite.txt`: pytest sobre Windows/Python 3.14.3, 6,141 passed, 11 skipped, 2 warnings, 0 failed, 1019.94 s; exit 0 consignado por ejecutor | **ACEPTADO como resultado local documentado**, no como certificación multiplataforma. |
| H-QA-04 arquitectura | `R1B-CIERRE-arch.txt`: `ok=true`, `broken_ports=[]`, `new_off_port_crossings=[]`, `off_port_total=5`, `off_port_baseline=5` | **ACEPTADO** para invariantes definidos en esta ronda. Permanecen cinco cruces conocidos D–H como deuda posterior. |
| H-QA-05 CI | Estado GitHub Actions del SHA `3913baa`: workflow `40168207630` en `queued`, sin conclusión al comprobar; runs anteriores también en cola | **PENDIENTE**. No declarar CI aprobada ni producto publicable. |

## Decisión QA

**ACEPTADO CON OBSERVACIONES: cierre técnico LOCAL de ronda 1B.**

Esta decisión **no equivale a** autorizar merge a `main`, declarar la distribución lista, emitir un release estable, certificar compatibilidad Linux/macOS ni afirmar paridad CLI–MCP. No requiere una nueva ronda 1B por los hallazgos locales ya cerrados a menos que aparezca nueva evidencia contradictoria.

**Observaciones de alcance y verificación:**

1. Los resultados de pruebas y gates son verificables documentalmente en GitHub, pero fueron ejecutados por el agente local. QA no los reprodujo en un entorno propio.
2. `R1B-CIERRE-entorno.md` documenta tres intentos fallidos antes del cuarto exitoso; esta trazabilidad se conserva y no invalida la última corrida.
3. Las pruebas se ejecutaron sobre el SHA de código `f24a9b8`; commits posteriores agregan evidencias/informe, no modifican código según el diff revisado. El SHA del HEAD ejecutor es `3913baa`.
4. Las 11 omisiones y dos warnings deben mantenerse visibles; no equivalen a fallos de suite en el alcance informado.
5. La cobertura de otras versiones de Python y plataformas, integración CI y criterios de empaquetado/distribución quedan pendientes para la fase posterior.
6. Los cinco cruces fuera de puerto conocidos D–H permanecen como deuda vigilada, no como nuevas regresiones.

## Comunicación y siguiente ronda

- **QA** conserva la propiedad editorial de `audits/handoff/RESPUESTA-QA.md`.
- **Ejecutor** conserva la propiedad de `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` y sus logs.
- **Propietario** decide autorización de la próxima ronda, cambios en `main`, lanzamiento y prioridad entre deuda arquitectónica (Q04–Q07) y preparación para distribución.
- **No iniciar Q04–Q07 automáticamente** ni hacer merge de PR #1 a `main`.
- Una vez disponible CI para el SHA de la rama, verificar estado, matriz multiplataforma, dependencias de wheel (incluido PyYAML) y pruebas JSON-RPC; registrar evidencia antes de solicitar autorización de distribución.
- Para producto CLI + MCP, programar en fase independiente una validación de instalación limpia, operaciones E2E reales y paridad de contratos/adaptadores.

**Estado:** RONDA 1B CERRADA EN ALCANCE LOCAL; CI Y RELEASE PENDIENTES.


---

# Fase 2 · Dictamen independiente L3 (2026-10-25)

**Revisor:** QA arquitectónico (ChatGPT) · **Rama:** `fase2/deuda-y-product-readiness-20261025`  
**SHA inspeccionado:** `44f6f893670d8080703342878aca465650987604` · **Ámbito:** lectura de commits, workflow, código del harness y logs publicados en GitHub. **QA no ejecutó localmente estos tests.**

## Dictamen

**L3: REQUIERE AJUSTES PARA SU CIERRE DOCUMENTAL Y DE QUALITY GATE; recorrido funcional local DEMOSTRADO POR EVIDENCIA DEL EJECUTOR.**

Aceptamos como evidencia del ejecutor: recorrido MVP 16/16 en Windows/Python 3.14.3/Node 24; cinco casos de paridad con los campos normalizados declarados; `AP-40` exit 0 en el log; prueba local antes/después de TD-0001 (`ModuleNotFoundError: yaml` → dos product gates PASS); ausencia de archivos `mcp-trace-log.*` en wheel de 705 miembros. Estas pruebas **no certifican** funcionamiento de las 97 tools ni multiplataforma.

### Observaciones correctivas obligatorias

1. **H-L3-01 · Higiene de evidencias (P2 de exposición):** `audits/fase2/logs/L3-TD0001-antes.txt` y `L3-TD0001-despues.txt` contienen rutas absolutas locales con identificadores personales. El original incluso contiene secuencias UTF-16/NUL embebidas que pueden eludir un saneamiento basado en texto UTF-8. Sanear los logs publicados, evitando incluir nombres personales, directorios de usuario, secretos y rutas físicas; convertir limpiamente la codificación sin eliminar traceback, fallos, comandos, exit codes o prueba de resolución en `site-packages`. Revisar cualquier log adicional de L3. Al estar ya publicados, evaluar también el historial Git y el mecanismo adecuado para contener futuras filtraciones sin reescribir historia de forma unilateral. Si se identifican credenciales, escalar inmediatamente a respuesta a incidentes, no publicar las credenciales en el informe.
2. **H-L3-02 · False green del harness de paridad (P1 para validez de QG-05):** `audits/fase2/paridad_cli_mcp.py` solo utiliza `coincidencias == casos` para su exit code y no exige `contrato_ap40.exit == 0`. El criterio `_elegir` omite claves inexistentes y los casos de lectura/búsqueda son mayormente vacíos; por eso puede existir un verde engañoso si ambas respuestas omiten campos o si AP-40 falla. Corregir fail-closed y agregar pruebas negativas deliberadas: inyectar fallo de AP-40, ausencia de campo obligatorio y divergencia de error/efecto; cada condición debe producir `exit != 0`. Comparar efectos observables del archivo/runtime antes y después de operaciones de escritura; no presentar la lista de 97 como paridad semántica total.
3. **H-L3-03 · Timeout del cliente MCP de prueba (P2):** `recorrido_mvp.py` compara contra una fecha límite, pero usa `stdout.readline()` bloqueante, que no respeta necesariamente el plazo. Lo mismo puede ocurrir en `paridad_cli_mcp.py`. Registrar como nueva deuda de confiabilidad del harness; proponer y probar un timeout real de proceso/I/O. No es defecto demostrado del servidor MCP.
4. **H-L3-04 · CI pendiente (bloqueo de QG-07):** el YAML incorpora una instalación de wheel antes de los Product Gates, compatible sintácticamente con runners Bash en Windows/Linux/macOS, pero la matriz no tiene ejecución concluyente para este SHA. No declarar TD-0001 `corregida` para CI ni QG-06 multiplataforma PASS todavía.

### Decisiones recomendadas al propietario (sin ejecutarlas unilateralmente)

- **PR de fase 2:** autorizar un **draft PR** desde `fase2/deuda-y-product-readiness-20261025` hacia `main` únicamente para activar `pull_request` y revisión; **prohibir merge/auto-merge**. Informar que el diff acumula la rama auditada de ronda 1B (aproximadamente 43 commits / 60 archivos frente a main en la comprobación QA), porque el PR #1 aún no se ha fusionado. No exigir que CI concluya para continuar investigación; mantener QG-07 BLOCKED.
- **Siguiente lote:** L2, **solo investigación Q04–Q07**, sin modificar el producto ni alterar los contratos hasta un nuevo dictamen. Antes o como corrección independiente inmediata, cerrar H-L3-01 y H-L3-02; no arrastrar esas evidencias deficientes a la aceptación de fase 2.

## Criterios para cerrar las observaciones de L3

Evidencia saneada verificable y prueba de que el harness falla cuando debe fallar. Añadir commit(s) separados con pruebas negativas y reporte breve en `RESPUESTA-DEL-EJECUTOR.md`. QA reevaluará; la evidencia funcional ya probada no necesita repetirse si no cambian los contratos/artefactos que mide.

**Estado:** L3 CON AVANCE FUNCIONAL CONFIRMADO, QA FINAL PENDIENTE DE CORRECCIONES; CI Y RELEASE BLOQUEADOS.



---

# Dictamen QA — Fase 2: correcciones L3 + investigación L2 (2026-10-25)

**Rama:** `fase2/deuda-y-product-readiness-20261025`  
**SHA del ejecutor revisado:** `1c788e36b7e5dacb4c66a68303d794020118b190`  
**Revisión independiente:** comparación de commits, análisis de código, pruebas, logs y estados de PR/Actions mediante GitHub. QA **no ejecutó la suite localmente**.

## Verificación

- **PR #2:** abierto en borrador, sin fusionar; PR #1 también abierto y sin fusionar. `origin/main` permanece en `1c34754258441550139ce895e182ab219c93f9bb`.
- **L3/H-L3-01:** los logs del HEAD actual están saneados según el informe y se agregó el verificador `comprobar_saneamiento.py`; el ejecutor reportó 8 pruebas aprobadas.
- **L3/H-L3-02:** `evaluar()` exige AP-40 exit 0 y compara presencia de campos, errores MCP, valores y casos requeridos; se publicaron 11 pruebas y una corrida real 5/5. Sigue habiendo huecos de cobertura descritos abajo.
- **L3/H-L3-03:** lectura MCP pasa a hilo + cola, y hay prueba de proceso mudo con timeout; corrección razonable para el silencio total. Un flujo constante de líneas no pertinentes puede prolongar `queue.get(timeout=...)` porque el contador se reinicia en cada iteración.
- **L2/Q04–Q07:** demostración documentada en `audits/fase2/logs/L2-control-degradado.json`: AP-40, AP-42 y AP-43 desaparecen de `by_norm` si se rompe la dependencia, sin estado de ejecución en el envelope. Se propone inversión de dependencia + contrato de estados, sin cambios al producto. La salida CLI exit 0 sigue siendo inferencia por lectura, no prueba ejecutada.
- **CI:** tres runs asociados a fase 2 siguen en `queued` y sin conclusión. QG-07 permanece bloqueada.

## Nuevos hallazgos QA

**H-L3-04 — Declaración de exposición histórica contradicha (P2: privacidad/evidencia).** El antiguo blob de `audits/fase2/logs/L3-TD0001-antes.txt` en el commit público `44f6f893670d8080703342878aca465650987604` contiene una ruta `C:\\Users\\...` con un nombre de cuenta real y bytes NUL/UTF-16. En el HEAD actual el archivo está saneado, pero la versión histórica continúa disponible. Por tanto, la afirmación «0 ficheros con ruta real o nombre en ninguna rama publicada» **no está demostrada y es materialmente incorrecta para el historial de commits**. No volver a publicar la ruta ni el nombre en logs. Reinspeccionar **historia completa** (`git rev-list --all` + árboles/blobs relevantes), distinguir estado actual/historia pública, y entregar un registro saneado de ruta, SHA y categoría de exposición. No reescribir historia, borrar refs ni hacer force-push sin decisión explícita del propietario. Sin evidencia de token o secreto no presumir compromisos de credenciales.

**H-L3-05 — Casos repetidos y efectos reales sin verificación suficiente en paridad (P2: robustez del Quality Gate).** `evaluar()` usa un conjunto de nombres (`{f.get("operacion") for f in filas}`), por lo que dos escenarios de `vault_write` de `CASOS` no tienen identidad propia: faltar uno no produce necesariamente fallo. Corregir asignando `case_id` único (operación + escenario) y exigir ejecución de cada ID, sin duplicados inesperados; agregar prueba negativa de caso duplicado/omitido. Comparar también evidencia del estado observable (hash/contenido de archivos y cambios normalizados antes/después por CLI y MCP, con aislamiento); los campos `created/updated/path` solo prueban concordancia declarativa de las respuestas. Verificar también inconsistencia entre código de salida CLI y envelope de éxito cuando corresponda. No inferir equivalencia funcional total de 97 herramientas.

**H-L3-06 — Timeout por plazo global (P3, mejora de robustez del harness).** `queue.get(timeout=timeout)` dentro del ciclo usa el timeout completo por cada línea. Bajo notificaciones o tráfico irrelevante reiterado, el límite total puede superarse. Recomendar deadline monotónico único y caso adversarial de mensajes sin ID coincidente. No se clasifica como defecto del servidor MCP.

## Decisión QA

- **L3:** `REQUIERE CORRECCIONES` de H-L3-04 y H-L3-05 para aceptación final del lote. El recorrido MVP 16/16 y las correcciones H-L3-01–03 quedan reconocidas **en su alcance local reportado**, sin repetirlas salvo cambios funcionales relevantes. H-L3-06 es P3, diferible con seguimiento.
- **L2:** `ACEPTADO CON OBSERVACIONES COMO INVESTIGACIÓN`. La causa y dirección arquitectónica de TD-0003 son sustentadas; faltan inventario completo de consumidores, especificación contractual compatible y demostración real de comportamiento de puerta/exit-code antes de autorizar implementación de Q04–Q07.
- **Q04–Q07:** **NO AUTORIZADAS para implementación** en esta revisión; solo diseño y pruebas propuestas.
- **L4:** queda a decisión del propietario autorizar el lote documental, seguridad e historia, sin modificar main ni emitir release.
- **QG-07 / RELEASE:** `BLOCKED` por CI sin validación multiplataforma y por controles pendientes.

## Comunicación requerida del ejecutor

El ejecutor debe reconocer este dictamen en `RESPUESTA-DEL-EJECUTOR.md`, anexar evidencias saneadas, SHAs, pruebas negativas y justificación de lo que cambia, con commits aislados. QA revisará el cierre de H-L3-04/H-L3-05 antes de aceptar L3. No publicar datos identificables durante la investigación y no alterar `RESPUESTA-QA.md`.

**Estado final:** L2 investigación aceptada con observaciones; L3 correcciones exigidas; CI y lanzamiento pendientes.


---

# Dictamen QA — Entrega final de planificación y diagnóstico Fase 2 (2026-10-25)

**Revisor:** QA independiente, ChatGPT. **Rama:** `fase2/deuda-y-product-readiness-20261025`.
**SHA ejecutor inspeccionado:** `e5e1b48ea9cc2446d04b23bbf40bc3f5693a76fd`.
**Método:** consulta de GitHub (commits, diffs, archivos, propuestas QG, informes, PR y GitHub Actions); NO ejecución local independiente de suite, CI ni pruebas de seguridad.

## Decisión de QA

**FASE 2 — ENTREGA DEL DIAGNÓSTICO/DISEÑO ACEPTADA CON OBSERVACIONES; CIERRE DE CALIDAD DEL PRODUCTO NO APROBADO.**

Se verifica la entrega y publicación de los ocho commits posteriores al dictamen `b680ac8`. Los trabajos asignados de documentación y diseño están presentes, pero **L4 es una auditoría parcial** (PRD CLI, PRD MCP y contrato de runtime sin contraste declaración por declaración; seguridad de dependencias y sdist no ejecutadas; buena parte de los gaps históricos sin clasificar). La propuesta `catalogo-qg.yaml` está redactada, **no constituye un ejecutor de decisiones aprobado o probado**.

| Área | Juicio |
|---|---|
| H-L3-05 | Identidad de escenario y comparación normalizada de efectos implementadas, 17 tests reportados, con brecha nueva en detección de cambios externos |
| H-L3-06 | Timeout global monotónico documentado y 5 tests reportados: aceptado en alcance del harness |
| H-L3-04 | Inventario histórico publicado y corrección de afirmación anterior: parcial, aún tiene déficit de cobertura y una divulgación evitable en el propio auditor |
| L2 TD-0003 | Diseño de inversión + estados y migración entregado: aceptado como **propuesta**, NO autorizado para implementar Q04–Q07 |
| L4 | Diagnóstico parcial y deuda nueva documentada; no declarar auditoría de seguridad o revisión completa de PRD |
| QG-00..07 | Catálogo de propuesta entregado; corregir coherencia de reglas antes de adoptarlo como control operativo |
| TD-0008 | P1 vigente: `vault_init --clean` puede borrar contenido sin respaldo; un release para terceros no puede ignorarlo |
| CI | Sin conclusión para SHA final; run `40178109786` en cola cuando se consultó. QG-07 BLOCKED |
| Git | PR #2 DRAFT sin fusionar; PR #1 sin fusionar; `main` en `1c34754258441550139ce895e182ab219c93f9bb` |

## Hallazgos adicionales concretos del QA

**H-F2-01 — Saneamiento y cobertura del auditor histórico, severidad P2.**
`audits/fase2/auditar_exposicion_historica.py` lleva incrustado en `NOMBRE` un patrón de expresión regular que codifica literalmente un identificador personal. Este archivo `.py` público queda fuera del verificador que busca nombres en prosa o registros de texto, y reproduce información que la auditoría pretendía no exponer. Sustituir por un criterio no personalizado (o marcadores inertes en pruebas), sin escribir el dato personal en nuevas evidencias. Adicionalmente `commits_que_tocaron_evidencias()` parte de `git log --all --full-history -- audits/fase2/logs audits/handoff/logs`: revisa commits que tocaron esos directorios, **no todos los blobs en toda la historia del repositorio**. Declarar ese alcance limitado, o ampliar el escaneo programáticamente. La afirmación "0 secretos" solo vale para los patrones y los blobs efectivamente inspeccionados, no como garantía universal. No forzar reescritura de Git; el propietario decide sobre exposición histórica y privacidad.

**H-F2-02 — Detección incompleta de efectos FUERA del runtime, severidad P1 de confianza en QG-05/04.**
En `audits/fase2/paridad_cli_mcp.py`, las expresiones `fuera_cli` y `fuera_mcp` hacen diferencia de **sets de rutas**, no de mapas ruta→hash. Por tanto detectan algunos ficheros nuevos fuera del runtime, pero **no** una modificación de contenido de un fichero externo preexistente ni una eliminación externa. El test de la bandera `fuera_del_runtime` no prueba que el recolector detecte estos cambios reales. Corregir la medición (creados/modificados/eliminados y hashes), aislar el directorio de prueba, añadir prueba negativa con un archivo externo preexistente alterado y otra de borrado externo. Hasta entonces no proclamar que el harness demuestra ausencia de cualquier escritura fuera del runtime.

**H-F2-03 — Política QG todavía no apta para ser aplicada, severidad P2.**
`QG-07` exige `QG-01..QG-06` pero omite explícitamente `QG-00`, pese a que éste dice bloquear las demás puertas. `QG-02` contiene TD-0003 como check **pendiente** y a la vez permite PASS por 26/26 + sandbox, sin demostrar ejecución real de AP-40/42/43. Formalizar la evaluación `NOT_RUN/BLOCKED/FAIL` de controles obligatorios, requisitos de evidencia del **SHA real** y pruebas de que un control degradado **nunca** se presenta como PASS. Esto es una corrección de contrato/diseño del QG, no permiso para implementar el runtime de TD-0003.

## Siguientes decisiones (NO ejecutar automáticamente)

1. **Propietario**: decidir la retención o saneamiento histórico de los blobs públicos. No reescribir historia ni force-push sin autorización expresa.
2. **QA/ejecutor, una vez autorizado**: corregir H-F2-01 y H-F2-02 en commits individuales con pruebas y evidencias; ajustar H-F2-03 en el catálogo y pruebas de política. No destruir datos reales; validar en sandboxes descartables.
3. **Propietario**: priorizar la corrección segura y reversible de TD-0008 (con backup y recuperación) antes de cualquier beta de terceros.
4. **TD-0003/Q04–Q07**: preparar autorización específica de implementación tras especificación compatible y pruebas de consumidores; no se considera corregida hoy.
5. **Producto**: cerrar revisión PRD por afirmación, seguridad, dependencias/sdist y CI multiplataforma. Mantener PR #2 como borrador, no fusionar PR #1/#2 sin decisión.
6. **Release**: QG-07 continúa `BLOCKED`; no afirmar compatibilidad multiplataforma ni release listo.

**Esta revisión no modificó código de producto.** Se registra solamente el dictamen de QA en su buzón con el SHA del ejecutor anterior al commit de QA.
