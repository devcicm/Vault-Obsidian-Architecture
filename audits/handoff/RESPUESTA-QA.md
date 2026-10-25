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


---

# Dictamen QA — R01–R05 de fase 2, SHA cc787f9 (2026-10-25)

**Rama examinada:** `fase2/deuda-y-product-readiness-20261025`  
**SHA del ejecutor:** `cc787f9d6f27e64cdea247d76739b629a92333d7`  
**Método:** revisión independiente de commits, diff, código, instrumentos, informe y logs publicados; estado de PR y Actions mediante GitHub. **QA no ejecutó la suite localmente ni certificó seguridad de todo el repositorio.**  
**Decisión:** **REMediación R01–R05 ENTREGADA, NO ACEPTADA COMO QUALITY GATE INTEGRAL; REQUIERE CORRECCIONES ANTES DE DECLARAR QA CONFORME.**

## 1. Resultado confirmado

- Nueve commits nuevos sobre el dictamen `2b8c87d`, rama aislada en SHA `cc787f9`.
- `main` sigue en `1c34754258441550139ce895e182ab219c93f9bb`; PR #1 abierto y sin fusionar; PR #2 abierto en DRAFT y sin fusionar.
- El ejecutor reporta `6184 passed, 5 failed, 12 skipped` y puertas `25/26`; QA **no sustituye** fallos por PASS aunque sean preexistentes.
- Los cinco fallos locales comparten causa atribuida por el ejecutor a AP-57. En el código de `vault_criterios.py`, `EXT_EJECUTABLES` incluye `.yaml/.yml`, y `medir_fronteras()` marca como `frontera_no_declarada` los YAML fuera de zonas. Debe demostrarse la clasificación correcta de **YAML de datos vs YAML ejecutable** mediante tests; no eximir `audits/fase2/` en bloque, ni ampliar baseline.
- TD-0003/Q04–Q07 **sin implementar**, QG-02 `BLOCKED`; TD-0008 `--clean` potencialmente destructivo **solo diseñado**, aún P1 vigente; CI de SHA `cc787f9` run `40188756147` y sus jobs siguen `queued`, QG-07 `BLOCKED`.

## 2. Dictamen por entrega

| Unidad | Resultado QA |
|---|---|
| R01 auditor histórico | Código e instrumentos publicados; corrección de datos incrustados y pruebas reportadas. **ACEPTADO CON RESERVA de alcance**: el informe reclama cobertura por todos los blobs pero la versión final usa `git log -p` (parches/deltas), no lectura de cada blob completo. El docstring afirma incorrectamente que el parche contiene el blob completo para cada estado; la métrica `commits_escaneados` cuenta commits con hallazgos, no todos los commits examinados. Ajustar declaración, instrumentación y prueba de historia sin hallazgos. Sin reescritura histórica. |
| R02 efectos externos | Se introdujo hash antes/después y clasificación de creados, modificados y eliminados, pruebas negativas y medición local 5/5 reportadas. **ACEPTADO EN ALCANCE DEL HARNESS LOCAL**; mantener exclusiones y errores de lectura documentados. |
| R03 política de QG | Hay `politica_qg.py`, catálogo ajustado y 9 pruebas publicadas. **REQUIERE CORRECCIÓN**: la función `_evidencia_ajena()` devuelve `False` cuando falta `sha_objetivo` o `evidencias[gate].sha`. Así, un estado sintético de todos los gates PASS más `ci.conclusion=success` y `control_ejecucion.completo=true` puede devolver `liberable=true` **sin evidencias**, contradiciendo el contrato fail-closed de QG-00/QG-07. Cambiar a exigir evidencia existente y SHA objetivo válido, verificar cobertura de todos los gates obligatorios e incorporar tests negativos de datos faltantes. El estado siempre debe originarse en un colector confiable, no en declaraciones arbitrarias. |
| R04 TD-0008 | ADR de cuarentena/confirmación/rollback y 11 pruebas **propuestas** publicado; **ACEPTADO COMO DISEÑO**, no como corrección funcional. El comando actual sigue eliminando datos sin backup. |
| R05 informe y CI | Informe actualizado y rama publicada; validación integral **NO CONFORME** por cinco fallos y una puerta roja. CI todavía en cola. |

## 3. Nuevas observaciones y criterios de cierre

**H-F2-04 (P1 del sistema de QA): evidencia faltante tratada como válida.** Reproducir con pruebas unitarias usando `evidencias={}` y `sha_objetivo` ausente o vacío. Exigir `BLOCKED`, impedir `liberable=true`. No relajar tests ni publicar un release ante información no acreditada.

**H-F2-05 (P1 de integridad de Quality Gate AP-57): YAML de datos clasificados como código ejecutable.** En `vault_criterios.py`, separar clasificación por rol/ruta/contenido controlado: YAML de workflows sigue vigilado; inventarios YAML de solo datos no se convierten en `frontera_no_declarada`; archivo de CI mal ubicado y copia de criterio YAML siguen detectables. Acompañar tests negativos y positivos; prohibido eximir todo un directorio arbitrariamente y prohibido inflar baseline. Volver a ejecutar AP-57, sus tests y los 26 gates.

**H-F2-06 (P2 de trazabilidad): alcance histórico sobreafirmado.** La versión final `auditar_exposicion_historica.py` contiene `git log --all -p` limitado a prefijos; eso es historial de diffs en los prefijos, **no** inspección de blobs íntegros en todos los estados del repositorio. Además `commits_escaneados` deriva de `commits_vistos` que se agrega solo si hubo hallazgos. Reconciliar afirmaciones/documentación/instrumento y medir separados `commits_considerados`, `blobs_inspeccionados`, exclusiones y errores. No afirmar `0 secretos en toda la historia`; limitar la conclusión a lo efectivamente verificado.

## 4. Decisión ejecutiva y próximas autorizaciones

**NO ESTAMOS AL 100% EN QA.** El cierre del alcance de ejecución es una entrega comprobada, no certificación del producto. En la rama actual quedan:
1. AP-57 y cinco tests fallidos / puerta 26 pendiente.
2. QG-02 bloqueada hasta aplicar TD-0003 con estados de ejecución por control y probar consumidores.
3. QG-07 bloqueada hasta CI concluyente y demás QG en PASS, incluido QG-00 acreditado.
4. TD-0008 P1 sin implementar (riesgo de pérdida de datos con `--clean`).
5. H-F2-04 y H-F2-06 como defectos pendientes en el sistema de QA.
6. Documentación PRD, seguridad completa, historial de secretos, sdist y soporte multiplataforma siguen parcialmente/no verificados según L4.

**No autorizar release ni merge de PR #1/#2. No reescribir Git ni alterar datos reales sin decisión del propietario.** El ejecutor debe pedir autorización explícita para implementar TD-0003/Q04–Q07 y TD-0008; la remediación AP-57 y la política de evidencia pueden tratarse en lotes aislados tras la nueva orden. Publicar SHA, tests positivos y negativos, logs y reconsultar CI para cada lote. QA revisará de nuevo.

**Estado:** R01–R05 publicados; R02 aceptado en alcance del harness, R04 aceptado como diseño, R01 con reservas, R03 y QG global requieren correcciones. RELEASE / QA INTEGRAL: NO CONFORME / BLOQUEADO.


---

# Dictamen independiente QA — lote R06 y preparación para terceros (2026-10-25)

**Rama:** `fase2/deuda-y-product-readiness-20261025`  
**SHA examinado del ejecutor:** `d0befe6e9c143289a0878d07512b124450eadbc1`  
**Revisión:** lectura de commits, diff, código de verificadores, pruebas, registros publicados, configuración de distribución y estado de PR/GitHub Actions. **QA no volvió a ejecutar la suite, los 26 gates, ni la instalación completa de wheel en un entorno independiente.**

## Veredicto

**R06 ACEPTADO CON OBSERVACIONES DENTRO DE SU ALCANCE CORRECTIVO. PRODUCTO PARA TERCEROS Y QG-07 TODAVÍA BLOQUEADOS.**

| Hallazgo | Juicio QA | Evidencia |
|---|---|---|
| H-F2-04 | **CORREGIDO** para el evaluador de política: exige SHA objetivo de 7–40 hex, evidencia declarada por gate y coincidencia exacta de SHA; bloquea datos faltantes | `audits/fase2/politica_qg.py`, `tests/test_fase2_politica_qg.py` (15 tests reportados) |
| H-F2-05 | **CORREGIDO** en el alcance de AP-57: diferencia YAML de workflow frente a datos, sin eximir un directorio completo ni inflar baseline; mantiene cobertura de workflow mal ubicado | `scripts/vault_criterios.py`, `tests/test_criterios_yaml.py` (7 tests), `R06-dictamen-correcciones.txt` |
| H-F2-06 | **CORREGIDA LA SOBREAFIRMACIÓN**, no equivale a auditoría histórica exhaustiva: distingue 52 commits considerados, 10 con exposición, 64 archivos, 120 deltas y **0 blobs íntegros** | `audits/fase2/auditar_exposicion_historica.py`, informe y 11 tests reportados |

El ejecutor reporta `26/26` puertas y `6203 passed, 12 skipped, 0 failed` en Windows; el registro es suficiente para considerar el lote de remediación técnicamente entregado, **pero no sustituye un run de CI concluido ni una ejecución independiente**. No se reabren rondas anteriores sin regresión demostrable.

### Observaciones residuales — no invalidan R06, sí limitan el release

**OBS-R06-01 — Evidencia histórica desfasada.** El archivo `audits/fase2/logs/H-F2-01-exposicion-historica.json` incluye `estado_actual` con una anotación `nul_utf16` para el reporte `.txt`, y el `.txt` publicado conserva esa línea de la ejecución previa. Sin embargo, el `.txt` presente en el HEAD se obtiene por GitHub como UTF-8 sin NUL. La evidencia quedó *autorreferencial y no actualizada* tras la corrección. Antes de acreditar QG-00/QG-04, regenerar evidencia de forma determinista y documentar SHA de ejecución y diferencias entre artefacto actual e histórico, sin publicar identificadores privados. No afirmar que ese JSON describe exactamente el HEAD final.

**OBS-R06-02 — Política declarativa ≠ procedencia comprobada.** `politica_qg.evaluar_politica()` valida estructura/coincidencia de los SHA que el *llamador declara*, no comprueba que un archivo de evidencia exista, que corresponda a una ejecución real o que la CI indicada pertenezca al SHA objetivo. El caso positivo de tests alimenta un `PASS` simulado. Esta separación es válida para un evaluador puro, pero QG-00/QG-07 de release necesitan un **colector confiable** que verifique referencias/artifacts, SHA completo de commit, contexto/matriz de CI, estados observables y política de integridad, antes de suministrar el estado al evaluador.

**OBS-R06-03 — Cobertura histórica limitada.** El auditor inspecciona parches bajo prefijos de evidencia y no los blobs completos de toda la historia; `forma_secreto: 0` **no prueba ausencia universal de secretos**. La decisión sobre reescritura del historial permanece exclusivamente en el propietario; no hacer `force-push` ni publicar nombres o valores sensibles.

## Estado de Quality Gates respecto de una publicación

- **QG-00:** política corregida, pero falta acreditar ejecución/procedencia y evidencia vigente del SHA candidato.
- **QG-01:** arquitectura y AP-57 reportan PASS local; sin dictamen externo multiplataforma sobre RC.
- **QG-02: BLOCKED** mientras no se implementen TD-0003 y estados de ejecución reales de AP-40/42/43, con consumidores fail-closed.
- **QG-03:** suite `6203 passed / 0 failed` reportada localmente; TD-0008 de integridad de datos permanece como riesgo P1.
- **QG-04:** controles de seguridad parcialmente verificados; pendientes dependencias, symlinks/TOCTOU, superficie MCP/CLI y recuperación destructiva.
- **QG-05:** la paridad CLI↔MCP de **cinco escenarios** reporta conformidad local y AP-40 revisa contrato; no afirmar pruebas funcionales de 97 tools.
- **QG-06:** hay wheel probada localmente fuera del checkout en L3; no hay cierre concluyente de la matriz actual Windows/Linux/macOS y Python soportado.
- **QG-07: BLOCKED:** run GitHub Actions `40192432773` del SHA `d0befe6` seguía en `queued` al consultar; además faltan QG-02, seguridad, corrección de TD-0008 y evidencia de release.

## Trabajo mínimo para un producto distribuible a terceros

1. **Autorizar y aplicar TD-0008:** proteger `vault_init --clean` con preflight, backup/cuarentena verificable, confirmación explícita, rollback, fallos inyectados y retención de respaldo. Probar **solo en runtimes descartables**. Diseñado hoy, no implementado.
2. **Autorizar y aplicar TD-0003/Q04–Q07:** inversión de dependencias, `checks[]` y `completo` verdaderos, todos los controles obligatorios con estados verificables, consumidores strict/coherencia fail-closed, pruebas de fallo de dependencia y regresión contractual. Ninguna puerta se vuelve verde por declarar 0 violaciones cuando no pudo medir.
3. **CI externa:** diagnosticar cola mediante Actions/runners y conseguir run concluyente del **SHA de release candidate** para Windows/Linux/macOS y el intervalo de Python declarado; pruebas de wheel, MCP y producto instalado. No atribuir PASS a runs `queued`.
4. **Seguridad y recuperación:** completar inventario de operaciones destructivas, symlinks/TOCTOU, validación real de `inputSchema` MCP, token/orígenes de HTTP, escaneo de dependencias y artefactos sdist/wheel. Resolver o aceptar explícitamente riesgos residuales según la política QG.
5. **Experiencia de terceros:** corregir DOC-0001/TD-0009 (Quick Start checkout vs wheel), contrastar PRD CLI/MCP/runtime (DOC-0006), documentar instalación sin clonar repo, configuración de Node/MCP, upgrade, rollback/desinstalación y conservación de vault. Revisar coherencia del classifier `Production/Stable` frente a riesgos pendientes.
6. **Liberación trazable:** definir RC, versión/tag y artefacto publicable con hash y SBOM, checklist de instalación ajena (init, escribir/leer/actualizar/buscar, recuperación, persistencia y rechazo de rutas externas), verificaciones QG-00..QG-07 con procedencia real, y autorización explícita del propietario. No fusionar PR #1/#2 ni emitir release por este dictamen.

**Prioridad:** TD-0008 e integridad de datos, TD-0003 y veracidad de gobernanza, CI/seguridad, luego documentación/RC. La exposición histórica de rutas y nombre de cuenta no exige reescritura inmediata sin evidencia de credenciales; documentar y asumir o decidir saneamiento mediante acto expreso del propietario.

**Resultado:** H-F2-04/H-F2-05/H-F2-06 cerrados en alcance de su remediación; aceptación de release **NO** concedida. Este registro QA no modifica producto, tests, baselines, PR ni `main`.


---

# Dictamen QA independiente — Correcciones QA-RC-01f y QA-RC-02 (2026-10-25)

**SHA del ejecutor examinado:** `4595aea4c8284b523966cfb3ddde0c87cd7092aa`  
**Rama de trabajo:** `work/release-cli-mcp-20261025`  
**Rama aislada de QA:** `qa/review-release-cli-mcp-4595aea-20261025`.  
**Dictamen anterior:** `628df53afc8ee6cbe5d721ff5ac092330582bf8b` (QA-RC-01f).  
**Método:** contraste independiente en GitHub de los commits `2a98dfd` y `4595aea`, diff, código, casos de prueba y estado real del PR/Actions. **No se ha ejecutado localmente la suite, la wheel ni las pruebas de fallo de filesystem.**

## Decisión

**QA-RC-01f: ACEPTADO EN EL ALCANCE DE LA RUTA `VERIFY_BACKUP`, CON OBSERVACIONES DE ENTORNO.**
**QA-RC-02: PARCIAL; NO ACEPTADO PARA ACREDITAR QG DE RELEASE.**
**GOAL: EN PROGRESO; NO READY_FOR_QA INTEGRAL, NO MERGE, NO RELEASE.**

### QA-RC-01f — Corrección reconocida

- El flujo de `VERIFY_BACKUP` fallido distingue mecanismo `rename` de `copia`.
- Con `rename`, verifica el contenido restaurado contra el inventario original para declarar `ROLLBACK`; un `rename` fallido produce `RECUPERACION_PENDIENTE`.
- Con `copia`, preserva el directorio original y trata por separado la retirada de la copia no verificada; no la instala sobre el original.
- Tres pruebas nuevas en `tests/test_vault_init_clean.py` comprueban comportamiento en ambos mecanismos e incluyen postcondición. El ejecutor informa 22 PASS/1 SKIP; QA confirma la existencia y aserciones de los casos, **no su resultado ejecutado**.
- Limitación registrada: verificación de symlinks omitida en Windows sin permisos; aún se necesita recorrido en wheel instalada y validación multiplataforma cuando exista CI. No seguir reabriendo QA-RC-01f sin una regresión reproducible.

### QA-RC-02 — Cambios buenos pero insuficientes

Se confirma sustitución de la mera mención de SHA por un recibo JSON con `gate`, `target_sha`, `verifier`, `command`, `exit_code`, `status`, tiempos y `run_id`; hay verificaciones de hash cuando `artifact` está presente, prueba de working-tree limpio y bloqueo por control degradado/violaciones. Eso resuelve parte del defecto anterior, **pero persisten rutas donde un PASS puede originarse en una declaración no acreditada**:

**QA-RC-02a (P1): recibo sin artefacto es PASS.**
`leer_recibo()` solo valida `artifact_sha256` dentro de `if artefacto:`. Por tanto acepta como `ok=true` un recibo fabricado con `status=PASS`, `exit_code=0` y campos de texto, aunque no haya resultado de verificador ni artefacto. `tests/test_colector_qg.py::test_recibo_valido_acredita` lo ejercita: crea `_recibo(tmp_path, "QG-01")` **sin artefacto** y espera `ok=True`. También el caso `_entorno_completo` fabrica artefactos que contienen únicamente la cadena `salida de QG-xx`. El hash demuestra igualdad de bytes, **no cumplimiento del gate**.

**Cierre exigido:** el propio colector/orquestador debe ejecutar o recuperar resultados auténticos tipados de los verificadores obligatorios, evaluar salida estructurada por gate y validar artefacto/hashes/exit. Ningún QG obligatorio debe obtener PASS a partir de campos arbitrarios en un JSON. Introducir prueba negativa de recibo sintético `PASS/exit=0` sin artefacto, artefacto con `ok:false` y salida de otro verificador.

**QA-RC-02b (P1): CI incompleta o sin identidad puede pasar.**
`estado_ci()` admite `workflowName=None` como válido: `r.get("workflowName") in (None, workflow_esperado)`. Un run de `success` con el SHA y **sin nombre de workflow** puede acreditarse. Tampoco consulta jobs/estrategia/matriz: un run exitoso pero carente de los jobs obligatorios se toma como conclusión suficiente. La prueba positiva solo aporta un registro superficial del run.

**Cierre exigido:** exigir identificación positiva del workflow por ID o nombre validado, ejecución `completed/success`, y verificar cobertura y conclusión de la matriz obligatoria (`validate` y `product-gates` por 3 SO x 4 Python, y demás jobs requeridos). Negativas de workflow sin identidad, jobs ausentes o incompletos y matriz parcial. No convertir falta de permisos API en PASS.

**QA-RC-02c (P2): procedencia local todavía declarativa.**
`_procedencia_suite()` comprueba SHA y `exit=0` del recibo, pero no verifica el hash del XML ni que un ejecutor real lo emitiera. `checkout_en_sha()` compara stdout de git sin validar `returncode` de cada comando. `control_ejecucion()` no contrasta `p.returncode` antes de aceptar `completo` y `total_violations`; tampoco valida `checks` por sí mismo. El modelo de confianza local limitado está correctamente **declarado**, pero no debe describirse como certificación independiente.

**Cierre exigido:** atar el JUnit a un hash de artefacto generado en la ejecución, verificar return codes de git/ejecutores, y construir evidencias posteriores al SHA congelado fuera del árbol versionado. No introducir ciclos `commit ↔ recibo SHA`.

## Otros pendientes del GOAL

- **QA-RC-03:** cinco `off_port_crossings` declarados siguen vivos. Cambiar su carácter de `a_eliminar` a `permanentes` requiere **ratificación explícita del propietario**; el ejecutor no puede autoconceder una exención. Mantener los límites `objetivo` y la baseline hasta una decisión. Alternativamente cerrar en código los cruces mediante el propietario arquitectónico sin solo trasladar imports.
- **QA-RC-04:** PR #3 **OPEN/DRAFT**, `main` remoto en `1c34754258441550139ce895e182ab219c93f9bb`, sin merge. Run `40236711495` del SHA `4595aea` figura `queued` y sin conclusión; causalidad administrativa/facturación no demostrada. QG-07 `BLOCKED`.
- **QA-RC-05:** recorrido de `--clean` desde wheel instalada y actualización de un tercero, sin ejecutar sobre SHA nuevo.
- **Integración:** suite total/26 puertas y wheel/sdist finales no reejecutados/reconstruidos para `4595aea`. No acreditar pruebas del SHA `0580b7e` al actual.
- **Historia:** reescritura de blobs públicos con datos locales requiere decisión del propietario; no hacer force-push unilateral.

## Instrucción al ejecutor

**Continuar el GOAL sin detener trabajo técnico por CI.** Cerrar QA-RC-02a/b/c, luego QA-RC-03 con composición legítima o propuesta de excepción pendiente de aprobación del propietario, completar QA-RC-05 con wheel y entorno externo, congelar nuevo candidato y ejecutar secuencialmente puertas + suite + comprobaciones de seguridad. Los recibos de ese SHA deberán emitirse fuera del árbol a partir de verificaciones reales. Solicitar QA solo al terminar ese lote, con evidencia, no por cada pequeña corrección.

**Resultado formal:** QA-RC-01f aceptado en alcance de verificación estática; QA-RC-02 incompleto; QA-RC-03/05 pendientes; QG-07 bloqueado por CI. **No autorizar main ni release.**
