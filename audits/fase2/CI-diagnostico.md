# Diagnóstico de la CI — qué corre, qué falla y por qué

**Fecha:** 2026-10-26 (ronda R13) · **Repositorio:** `devcicm/Vault-Obsidian-Architecture`
**Conclusión:** la CI **corre**. La cuenta no estaba bloqueada: el diagnóstico
anterior de este fichero (2026-10-25) atribuyó a la facturación una cola que
era otra cosa —los jobs de macOS tardan mucho en recibir runner y, cuando lo
reciben, fallan con defectos reales del producto. Este documento sustituye a
aquel con la evidencia de la API y los logs de las corridas concluidas.

## 1. Estado medido de las corridas (API de GitHub, no suposiciones)

| Corrida | SHA | Éxitos | Fallos | Pendientes | Estado del run |
|---|---|---:|---:|---:|---|
| `40299732445` | `36c91e0` | 9 | 8 | 8 | `completed/failure` |
| `40317033977` | `9e0bcd7` | 9 | 8 | 8 | `completed/failure` |
| `40326462714` | `0fffbc3` | 13 | 3 | 9 | `completed/failure` |
| `40335869688` | `8b87b24` | 13 | 1 | 11 | `completed/failure` |
| `40340865847` | `408eb23` | **21** | **4** | 0 | `completed/failure` |
| `40349132455` | `dfc6a06` | 20 | 5 | 0 | `completed/failure` |
| `40420024458` | `9c65401` | **24** | **1** | 0 | las 4 columnas de macOS **pasan**; el rojo es el defecto nuevo R13-05 (Windows 3.10) |
| `40430269201` | `e198ffb` | **25** | **0** | 0 | `completed/success` — **matriz completa en verde** por primera vez |

**Lo que esto desmonta:** la hipótesis de la ronda anterior («la CI está
bloqueada por facturación»). Los jobs de Windows y de Linux **ejecutan y
terminan**; los de macOS **también ejecutan** (tardan en recibir runner: en
las corridas intermedias se les veía en `queued` durante horas, y ese estado
puntual se tomó por «no arranca»). Cuando por fin corren, fallan —y esos
fallos son del producto y del harness, no de la infraestructura.

**El cierre de la ronda:** la corrida del commit final `e198ffb`,
`40430269201`, terminó **completed/success con 25/25 jobs** — las cuatro
columnas de macOS verdes incluidas. El defecto R13-05 quedó verificado en la
misma corrida: la regresión del drenaje corre en las 12 columnas `Validate`
de la matriz completa.

## 2. Los defectos, con su ficha

| ID | Plataforma | Síntoma | Causa demostrada | Corrección | Regresión | Evidencia | Estado |
|---|---|---|---|---|---|---|---|
| **D1** (R12) | Windows + Linux | 18 tests rojos en las 8 columnas: `vault_changelog_check` daba «hash inexistente» a commits que sí existen | `actions/checkout@v4` hace clon **superficial** (`--depth=1`): los objetos históricos no están en el clon | `fetch-depth: 0` **solo** en `validate` | clon `--depth=1` local → 19 fallos; con historia → 129/129 | corrida `40299732445` | CORREGIDO (verde en la CI) |
| **D2** (R12) | Windows | MCP muerto: `TOOL_EXECUTION_FAILED` con `No module named 'yaml'` | el servidor elegía `py`, que en el runner resuelve el Python de la **imagen base** (sin PyYAML) | orden `python3`/`python`/`py` + sondeo `import yaml` + diagnóstico en arranque | 9/9 `test_mcp_runner`, 8/8 `test_mcp_instalado` | corrida `40299732445` | CORREGIDO |
| **D3** (R12) | Windows 3.9/3.10 | hijos de Python muertos: `_Py_HashRandomization_Init` | dos fixtures con `env` curado **sin `SystemRoot`** → `CryptGenRandom` falla en 3.9/3.10 | heredan la invariante del anfitrión | `py -3.9` sin SystemRoot → rc=1 con el stderr idéntico; 3.12/3.14 → rc=0 | corrida `40299732445` | CORREGIDO |
| **D7** (R12) | Linux | puerta `conteos` roja solo en Linux, con la suite verde | la **cifra de tests dependía del sistema** (2 parametrizaciones solo en Windows) | se colectan en todas las plataformas y se saltan fuera de Windows | comparación de las listas collectadas (local vs CI) | corrida `40317033977` | CORREGIDO |
| **D8** (R12) | Windows | paso «Containment audit» rojo: 13 violaciones en el sandbox | la CI construye el sandbox desde **nuestra semilla**, que escribía notas no canónicas | semilla canónica (status, secciones, `responsable`) | audit del sandbox: 14 → 1 (la externa); en CI 0 | corrida `40317033977` | CORREGIDO |
| **D9** (R12) | Windows | paso `vault_norms --list` rojo solo en Windows | `python -c` con comillas escapadas: PowerShell se las come al pasar el argumento | `shell: bash` (ya usado por otros pasos) + comillas simples | verificado en bash local y en CI (windows-3.12 en verde) | corrida `40326462714` | CORREGIDO |
| **D10** (R12) | Windows 3.11 | flake: «README.md not idempotent» | el test comparaba **el reloj** (`Generated at`), no el estado | se normaliza solo el instante | dos generaciones con 1,2 s de diferencia: crudo distinto, normalizado idéntico | corrida `40335869688` | CORREGIDO |
| **R13-01** | macOS (3.9-3.12) | `RuntimeError: el servicio no abrió el puerto` + 11 errores de fixture; el proceso quedaba **vivo y sin escuchar**, sin decir por qué | **sin causa demostrada** (el dictamen lo dice). Lo que sí se midió: el servicio arranca en 0,017 s en local; el test esperaba un puerto elegido por él (carrera) y agotaba 30 s sin reportar nada | el servicio **enlaza antes de publicar** el fichero de puerto (señal de readiness) y registra sus tiempos de arranque en stderr; el test pide puerto 0 (que lo elija el sistema), espera la señal y, si no llega, dice código de salida, liveness, puerto, fichero de puerto y stderr acotado, con el token redactado | `test_el_arranque_que_falla_dice_el_codigo_y_el_stderr` | corrida `40420024458` | CORREGIDO (verificado en la CI de R13) |
| **R13-02** | macOS (3.9-3.12) | `test_heal_legacy_paso_curar_todas_las_notas_legacy`: 5 escaneadas donde hay 3 | la cascada de cada escritura crea ficheros (`index.md` de sección, notas de sistema) **mientras el `rglob` perezoso sigue recorriendo**: en APFS los ve, en ext4/NTFS no. Reproducido en local: una segunda pasada contaba 6 | el inventario se **materializa** antes de curar y los artefactos derivados se excluyen por su dueño (`vault_registry.es_artefacto_derivado`); además el escaner **publica el inventario** (ruta, clase, motivo) | `test_heal_legacy_no_cuenta_lo_que_la_pasada_crea`, `test_heal_legacy_publica_el_inventario_exacto` | corrida `40420024458` | CORREGIDO (verificado en la CI de R13) |
| **R13-03a** | macOS 3.11 | `test_file_lock_no_deja_entrar_a_dos_procesos`: el segundo proceso **moría** con `OSError: [Errno 22] Invalid argument: .../.locks/contador.txt.lock` | en macOS, cuando `.locks/` se retira mientras otra ruta se resuelve, `mkdir` responde **EINVAL/ENOTDIR**; en Linux el mismo caso es ENOENT, que el código ya contemplaba. El proceso debía **esperar su turno** | EINVAL/ENOTDIR se compiten otra vez, con el plazo como único freno | `test_un_einval_al_crear_el_lock_se_compite_otra_vez` (positiva) y `test_un_einval_permanente_no_espera_sin_fin` (negativa) | corrida `40340865847` | CORREGIDO (verificado en la CI de R13) |
| **R13-03b** | Windows 3.10 | `test_backup_base64`: `shutil.Error: ... vault-sandbox/00_System/.locks` — el directorio desaparece mientras se copia | la copia del sandbox **vivo** se coge en mitad: otra prueba en paralelo toma y suelta locks | el estado de bloqueo es de **ejecución**, no de contenido: la copia lo ignora (igual que la auditoría del toolkit) | el mismo test, con la copia coherente | corrida `40349132455` | CORREGIDO (verificado en la CI de R13) |
| **R13-04** | (política, no plataforma) | toda conclusion de CI que no fuera `success` se etiquetaba `CI_PENDIENTE`, incluida una corrida **ya concluida en rojo** | el colector solo miraba runs exitosos: una CI `completed/failure` salia `no_verificable` y la política leia «pendiente» | tres clases en la política y el colector: `CI_PENDING` (en cola o en curso), `CI_FAILED` (concluida, con los jobs en rojo nombrados) y `CI_PASS` (conclusion `success`); fail-closed intacto | 4 tests de política + 2 del colector | corrida `40340865847` | CORREGIDO |
| **R13-05** | Windows 3.10 (verificación `40420024458`) | `test_una_peticion_de_navegador_se_rechaza_aun_con_token`: `ConnectionAbortedError: [WinError 10053]` en vez del **403** esperado | al rechazar (Origin ajeno → 403), el servicio cerraba la conexión con el **cuerpo sin leer**: el núcleo TCP responde RST y el cliente lee la conexión abortada, la respuesta la pierde. Carrera del RST contra la lectura: 1 de 8 columnas la vio | el camino de rechazo de SP-04 **drena el cuerpo** (`Content-Length`, acotado) antes de responder, en los tres rechazos y el 404 de `do_POST` | el propio test, pedido 5 veces | log del job `121911857070`; verificado en la corrida `40430269201` | CORREGIDO (verificado en la CI de R13) |

## 3. La clase de CI: tres, no una (R13)

El evaluador etiquetaba como `CI_PENDIENTE` cualquier conclusión que no fuera
`success`, **incluida una CI que ya había terminado con jobs rojos** — que es
lo que pasó con el candidato `408eb23` (4 columnas de macOS en rojo) y lo que
el dictamen Auditó como clasificación errónea. Ahora:

| Clase | Cuándo | Efecto |
|---|---|---|
| `CI_PENDING` | la corrida está en cola o en curso (o no hay dato) | QG-07 sigue BLOCKED |
| `CI_FAILED` | la corrida **concluyó** con fallos (`failure`, `cancelled`, `timed_out`…) | QG-07 sigue BLOCKED, y el motivo nombra los jobs en rojo |
| `CI_PASS` | la corrida concluyó en `success` (el verificador de la CI exige además la matriz completa) | QG-07 puede pasar si lo demás está en PASS |

La regla fail-closed no cambia: **solo `success` pasa**. Lo que cambia es que
un fallo se dice fallido y no se esconde detrás de una espera.

## 4. Qué NO se ha hecho (y por qué)

- No se han cancelado runs ni relanzado ejecuciones.
- No se ha atribuido PASS a ningún run que no lo tuviera.
- No se ha ampliado ninguna baseline ni relajado ninguna aserción.
- No se ha marcado el producto como multiplataforma: macOS ahora **ejecuta**, y
  lo que falla son defectos del producto que se corrigen y se comprueban.

## 5. Consecuencia sobre los Quality Gates

`QG-07` queda **BLOCKED** mientras la matriz no esté completa (25/25) y mientras
las decisiones del propietario sigan abiertas. Con la corrección de R13, la
matriz de macOS debe quedar verde; si algún job vuelve a fallar, el motivo
estaría en el log del job y en el artefacto JUnit que la CI publica por
columna.

## 6. Evidencia complementaria (sin CI)

- Matriz local de Windows sobre la wheel instalada.
- Contenido de wheel y sdist inspeccionado, con hash.
- Auditoría de dependencias con `pip-audit` en un entorno aislado.
- Recorrido de tercero desde una instalación limpia fuera del checkout.

Todo eso es **evidencia complementaria**, no sustituto de QG-07.
