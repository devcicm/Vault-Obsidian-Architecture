# Respuesta del ejecutor a QA — GOAL Release CLI + MCP (ronda R09, cierre técnico)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico
- **Fecha:** 2026-10-25
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `a9e0143b5e246e2766fece5273bd7bfa20632707`
- **SHA inicial de la ronda:** `29c1a15cfcb212dedbcf1b6794c238fd815a4aa5`
- **SHA CANDIDATO CONGELADO:** `31dfa462e87f5dcdb703e649e840e826a136ba50`
- **Árbol:** limpio en el SHA congelado; `main` intacta (`1c34754`); PR #1, #2 y #3 sin fusionar (#3 DRAFT)

## GOAL: RELEASE CLI + MCP PARA TERCEROS

**ESTADO: READY_FOR_QA_WITH_EXTERNAL_BLOCKER.** Las correcciones técnicas de
R09-A..D están ejecutadas, probadas y publicadas; las 26 puertas y la suite
completa están en verde sobre el SHA congelado; los recibos se emitieron
ejecutando los verificadores de verdad. **Los únicos pendientes son decisiones
del propietario y la CI externa**, y QG-00..QG-07 declaran su estado real
(abajo), sin PASS falso.

## QA-RC-02g — resultados independientes por subcheck (CERRADO, `532f19e`)

Cada subcheck tiene verificador, comando (o función interna), exit code,
artefacto **propio** y SHA-256; la puerta solo pasa si **todos** pasan. Se
eliminó la autocertificación (un `exit 0` repartido a los subchecks). Salida
vacía ⇒ `degradado`. El comando de pruebas se ejecuta como pytest
(`python -m pytest <fichero> -q`), no como script. Negativas: subcheck fallido,
no ejecutado, salida vacía, artefacto individual ausente, artefacto manipulado,
subcheck ausente, QG-04 sin `pip_audit`, QG-06 sin instalación limpia, QG-00
sin reconciliador.

## QA-RC-02h — CLI del colector (CERRADO, `532f19e`, `001120c`, `31dfa46`)

`main()` ya no pasa `jobs_ci` a `colectar()`. Nueva CLI `--ejecutar` (ejecuta
verificadores y emite recibos **fuera** del árbol) separada de la evaluación;
`--recibos`, `--e2e-json`, `--suite-xml`, `--pip-audit-python`,
`--paridad-venv/--paridad-runtime`; códigos de salida explícitos (2 en error de
argumentos) y JSON final válido. La identidad del checkout (HEAD == SHA y árbol
limpio) se verifica **antes** de ejecutar (los verificadores escriben
artefactos de runtime propios) y viaja al dictamen. Probada como **proceso
real** por subprocess.

## QA-RC-02i — CI vinculada al run exacto (CERRADO, `532f19e`)

Jobs del endpoint del run seleccionado, con paginación y `total_count`; sin
identidad de run, con conclusión nula, con duplicados, con jobs desconocidos o
con paginación incompleta no se acredita; sin jobs o sin permisos ⇒ BLOCKED.

## QA-RC-05 — recorrido completo de terceros (CERRADO, `5a8395c`)

Sandbox nuevo por ejecución; hash del **fichero persistido**; cuarentena
identificada por el conjunto antes/después; cliente MCP **secuencial** con ids
correlacionados y plazo global; restore en destino limpio comparado por
**inventario y hashes**; reinstalación que conserva los datos.
**Resultado real: 27/27 pasos.**

## SUITE / SKIPS / PUERTAS / RECORRIDO E2E (sobre el SHA congelado)

| Medición | Resultado |
|---|---|
| 26 puertas | **26/26 en verde** |
| Suite completa | **6270 passed · 13 skipped · 0 failed** (16:17) |
| Recorrido E2E | **27/27** |

Los 13 skips declaran no aplicable en este entorno (symlink sin privilegios,
MCP en vivo sin su variable, etc.).

## WHEEL / SDIST / HASHES

| Artefacto | sha256 |
|---|---|
| `vault_obsidian_architecture-41.23-py3-none-any.whl` | `858f14073563d0f9ec81e5347bbf58637028da0575da758e7f9c00057815d9c1` |
| `vault_obsidian_architecture-41.23.tar.gz` | `22cf5d0c749499ecff040436f05b77df83552d29fe5ee4e691472c068d02d472` |

## QUALITY GATES — estado auténtico del SHA `31dfa46`

| QG | Estado | Evidencia / motivo |
|---|---|---|
| QG-00 | **BLOCKED** | su recibo es FAIL: el subcheck `reconciliador_archify` falla con **10 divergencias de inventario sin aceptar** (el snapshot de Archify, que documenta otra revisión, sigue apuntando a `vault_norms_engine` y las fichas del registro cambiaron al mover los cruces a `vault_norms`). `identidad_git`, `arbol_limpio` y `saneamiento`: ejecutados |
| QG-01 | **BLOCKED** | mismo reconciliador; `vault_arch`: ejecutado (ok) |
| QG-02 | **BLOCKED** | `puertas_26` y `auditoria_completa`: ejecutados (`completo: true`); `sin_violaciones`: **fallido** — la auditoría del sandbox canónico arroja 14 hallazgos (AP-07, AP-36, AP-64, CN-03) |
| QG-03 | **BLOCKED** | recibo PASS (suite JUnit con recibo de procedencia + recorrido E2E) pero bloqueado por el prerrequisito QG-00 |
| QG-04 | **BLOCKED** | recibo PASS (saneamiento, `pip_audit` sin vulnerabilidades, contención, operaciones destructivas) pero bloqueado por QG-00 |
| QG-05 | **BLOCKED** | recibo PASS (paridad CLI/MCP **5/5 CONFORME**, 97 tools MCP; AP-40 exit 0) pero bloqueado por QG-00 |
| QG-06 | **BLOCKED** | recibo PASS (construcción, contenido de la wheel, instalación limpia) pero bloqueado por QG-00 |
| QG-07 | **BLOCKED** | CI en `queued` (runs 40244460688, 40245587377, 40245754464 y posteriores) y prerrequisito QG-00 |

**Ningún PASS se declara sin ejecución real**: cada subcheck tiene su artefacto
y su hash en `%TEMP%\opencode\qg-recibos-final` (fuera del árbol versionado).

## CI / PR #3

- CI **queued**. Sin prueba concluyente no se atribuye la causa a facturación;
  el diagnóstico con evidencia de API está en `audits/fase2/CI-diagnostico.md`.
  La capacidad que falta es de la cuenta (Settings → Billing → Actions).
- PR #3 **DRAFT**, sin merge. PR #1 y #2 sin fusionar. `main` intacta.

## ARQUITECTURA (QA-RC-03) — DECISIONES DEL PROPIETARIO

1. **Ratificar o corregir el movimiento de los cinco cruces** de
   `vault_norms_engine` a `vault_norms`: el código distribuible ya no importa
   módulos excluidos (`shipped_imports_of_excluded: []`), pero el snapshot de
   Archify y las fichas del registro siguen describiendo el sitio anterior, y
   el reconciliador del repo lo refleja en 10 divergencias. Sin esta decisión
   QG-00 y QG-01 no acreditan.
2. **Fijar el contrato de QG-02**: ¿"cero violaciones" se mide sobre el sandbox
   canónico (que contiene 14 hallazgos deliberados) o sobre un runtime limpio
   de certificación? El dato medido está arriba; la decisión es del dueño.

Alternativas A/B/C con impacto, riesgo y recomendación:
`audits/fase2/ESTADO-RC.md`.

## SEGURIDAD

`pip_audit` sin vulnerabilidades conocidas (dependencia PyYAML); wheel sin
trazas, sin tests y sin material ajeno; contención verificada; operaciones
destructivas con rollback verificado por hash (23 pruebas).

## COMMITS

`532f19e` (02g/h/i) · `5a8395c` (recorrido de terceros) · `001120c` (identidad
del checkout) · `31dfa46` (subchecks derivados y verificadores especiales) ·
este informe.

## RECIBOS / EVIDENCIAS

- Recibos externos (`%TEMP%\opencode\qg-recibos-final`): un artefacto + sha256
  por subcheck y manifiesto agregado por puerta.
- JUnit de la suite + recibo de procedencia (`sha`, `exit`, `junit_sha256`).
- `audits/fase2/{colector_qg.py, recorrido_terceros_r07.py, ESTADO-RC.md,
  CI-diagnostico.md}`, `tests/test_colector_qg.py` (30),
  `tests/test_vault_init_clean.py` (23).

## RIESGOS

- QG-07 depende de una CI que no se ejecuta.
- QG-00/QG-01 dependen de la decisión del propietario sobre el inventario.
- El auditor histórico mide parches, no blobs (`forma_secreto: 0` no prueba
  ausencia universal).

## BLOQUEOS EXTERNOS

1. CI en cola (acción del propietario sobre la cuenta).
2. Ratificación del movimiento de los cruces (QG-00/QG-01) y del contrato de
   QG-02.
3. Decisión sobre reescritura de historia.

**SOLICITUD QA: SÍ** — revisión independiente del SHA congelado `31dfa46`, con
los recibos externos y las 10 divergencias de inventario pendientes de decisión.

---

# Respuesta del ejecutor a QA — fase 2, remediación post-QA (R01–R05)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico
- **Fecha:** 2026-10-25
- **Rama:** `fase2/deuda-y-product-readiness-20261025`
- **SHA del dictamen QA:** `2b8c87d`
- **SHA base de ejecución:** `2b8c87d`
- **SHA final publicado:** el commit de este documento (R05)
- **SO / terminal / Python:** Windows, PowerShell 5, Python 3.14.3
- **Estado del árbol:** sin cambios pendientes al cerrar
- **`main`, PR #1 y PR #2:** intactos; sin fusionar; sin `reset --hard` ni `push --force`

## Alcance ejecutado (R01–R05)

R01, R02 y R03 son correcciones efectivas. R04 es **solo diseño**: `scripts/vault_init.py` no se ha tocado.
TD-0003 y Q04–Q07 siguen sin implementar, por orden expresa.

| Tarea | Estado | Commit | Qué resuelve | Evidencia |
|---|---|---|---|---|
| R01 / H-F2-01 | COMPLETADA | `b9fb71d` + `dc63367` | El identificador personal ya no está incrustado (se deriva del entorno) y la cobertura pasa a blobs de toda la historia; 10 pruebas | `logs/H-F2-01-exposicion-historica.{json,txt}`, `logs/R01-auditor-historico.txt` |
| R02 / H-F2-02 | COMPLETADA | `08f9746` + `6a3ab78` | Los efectos externos se detectan por hash de contenido (creados/modificados/eliminados), con la lectura fallida como no verificable; 23 pruebas | `logs/L3-paridad-cli-mcp.txt` (5/5 CONFORME) |
| R03 / H-F2-03 | COMPLETADA | `2b5d141` | La política de QG se ejecuta: QG-00 prerrequisito, QG-02 condicionado por TD-0003, QG-07 con CI concluyente; 9 pruebas negativas | `logs/R03-politica-qg.txt` |
| R04 / TD-0008 | DISEÑO | `584470e` | Cuarentena atómica, máquina de estados de 8 fases con rollback, `--confirm`, 11 pruebas propuestas; sin cambio de comportamiento | `R04-diseno-td0008.md` |
| R05 | COMPLETADA | `24eb0a9`, `116595c` y este commit | Higiene de publicación (el auditor ya no reproduce nombres; fixtures compuestos en runtime) y carga por ruta de los instrumentos de `audits/fase2/`; buzón e informe de cierre | `logs/R05-cierre-orden.txt` |

## Verificación ejecutada

| Verificación | Resultado |
|---|---|
| `python -m pytest tests/test_fase2_hf201_privacidad.py` | 10 passed |
| `python -m pytest tests/test_fase2_paridad_fail_closed.py` | 23 passed |
| `python -m pytest tests/test_fase2_politica_qg.py` | 9 passed |
| `python audits/fase2/comprobar_saneamiento.py` | exit 0 |
| `python scripts/vault_gate.py --strict` | **25/26** — `criterios` (AP-57) rojo |
| `python -m pytest tests/ -q -n auto --tb=short` | **5 failed, 6184 passed, 12 skipped** — los 5 son los de AP-57 ya reproducidos en `2b8c87d` |

**El rojo de `criterios` es preexistente**, no de esta orden: se reprodujo igual en un worktree
`--detach 2b8c87d` (los mismos 3 `.yaml` de evidencia leídos como `frontera_no_declarada`).
No se ha ampliado ninguna baseline ni deshabilitado ninguna puerta.

## CI

Los cinco runs de la rama siguen en `queued` (el último, `40183930953` / `6a3ab78`). No se ha
cancelado ni relanzado ninguno, ni se ha modificado ningún workflow. Por ello **QG-07 = BLOCKED**
con `CI_PENDIENTE`, tal como aplica el evaluador de R03.

## Bloqueos

1. **CI en cola** → QG-07 BLOCKED (dato del proveedor).
2. **`criterios` / AP-57**: falso positivo preexistente sobre 3 YAML de datos; su corrección exige
   decidir el criterio del guard y añadir su test (fuera del alcance de esta orden).
3. **TD-0003**: QG-02 BLOCKED mientras el envelope no publique el estado de ejecución por control.
4. **Exposición histórica**: sigue en los blobs publicados; reescribir historia requiere autorización
   del propietario.

## Solicitud de QA

Revisar R01–R04, y decidir (a) el tratamiento del falso positivo de `criterios` y (b) la autorización
del diseño de TD-0008 para pasar a implementación.

---

## Lote de correcciones del dictamen QA (H-F2-04, H-F2-05, H-F2-06)

Publicado sobre el dictamen `cb3233a`, en commits separados:

| Hallazgo | Corrección | Commit | Evidencia |
|---|---|---|---|
| **H-F2-04** (P1) — la política daba `liberable=true` sin SHA ni evidencias | `sha_objetivo` obligatorio (7-40 hex) + evidencia obligatoria por gate; ausente → `EVIDENCIA_AUSENTE`, de otro SHA → `EVIDENCIA_DE_OTRO_SHA` | `0a583da` | 15 pruebas; repro posterior da `liberable=false` |
| **H-F2-05** (P1) — YAML de datos leído como frontera ejecutable (AP-57) | `yaml_es_ejecutable()`: `.github/` = ejecutable; claves de primer nivel de workflow = ejecutable aunque esté mal ubicado; resto = datos | `8b01bdb` | 7 pruebas nuevas; 50 passed en AP-57/AP-46; `criterios` ok, `new_copies []`, baseline 2 |
| **H-F2-06** (P2) — alcance histórico sobreafirmado | Se inspeccionan **parches** (declarado), `blobs_inspeccionados=0`, métricas separadas (`commits_considerados=52`, `con_exposicion=10`, `ficheros=64`, `deltas=120`, `errores=0`) y prueba de historia sin hallazgos | `d175917` | `logs/H-F2-01-exposicion-historica.{json,txt}`, `logs/R01-auditor-historico.txt` |

**Registro canónico:** `TD-0010`, `TD-0011` y `TD-0012` en `audits/fase2/inventario-deuda.yaml`, estado `corregida` con su commit.
**Informe del lote:** `audits/fase2/logs/R06-dictamen-correcciones.txt`.

**Verificación de este lote:** puertas **26/26** (`vault_gate --strict`), suite completa **6203 passed / 12 skipped / 0 failed**, `comprobar_saneamiento` exit 0.

**Lo que sigue pendiente y por qué:** TD-0003/Q04–Q07 (cambio de producto, requiere autorización; QG-02 `BLOCKED`), TD-0008 (diseño publicado; `vault_init --clean` intacto, requiere autorización), CI en cola (QG-07 `BLOCKED` con `CI_PENDIENTE`) y la exposición histórica del blob de `b9fb71d`, que sólo el propietario puede decidir reescribir.

---

# Respuesta del ejecutor a QA — ronda 1B (histórico, se conserva)
- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico
- **Fecha:** 2026-10-25 (hora local del ejecutor, UTC-6)
- **Rama:** `audit/archify-governance-20261024`
- **SHA leído de instrucciones QA:** `bf4003f69bc84ac1ffa0fd13fc2bfe41045cc046` (dictamen de ronda 1)
- **SHA base de ejecución:** `bf4003f` (estado tras la sincronización E01)
- **SHA final publicado:** `559e204` (anexo de CI del cierre; la lista completa de commits de la ronda 1B está en la tabla de ejecución y en la sección de cierre técnico)
- **SO / terminal / Python:** Windows, PowerShell 5, Python 3.14.3
- **Estado del árbol local al terminar:** limpio (`git status --porcelain` vacío); `main` intacto, PR #1 sin fusionar
- **SHA base de la ronda 1 (referencia QA):** `f3aaafc34a4ca719070a55f642452d52c107b58d`

## Resumen de cambios

Siete commits publicados entre `bf4003f` y la publicación de este informe (uno por unidad, push tras cada uno):

| Tarea | Estado | Commit | Archivos | Pruebas | Resultado | Evidencia |
|---|---|---|---|---|---|---|
| E01 sincronización | COMPLETADA | `94bf46e` | `audits/handoff/logs/R1B-E01-sincronizacion.txt`, `audits/handoff/logs/2026-10-24-R1-respuesta-ejecutor.md` | `git merge --ff-only` (exit 0) | fast-forward limpio `f6a5387..bf4003f`, sin pérdidas; informe de ronda 1 preservado (QA lo leyó como plantilla) | `R1B-E01-sincronizacion.txt` |
| E02 observabilidad del ledger | COMPLETADA | `e925bef` | `tests/test_ap39_contrato.py` | unittest AP-39: 6/6 OK, exit 0 | `vocabulary_recorded == -1` y `vocabulary_introduced == [tag]` añadidos al caso del ledger roto; aserciones previas conservadas; no es vacua (None o >=0 harían caer el test) | `R1B-Q02-unittest.txt` |
| E03 precedencia de root | COMPLETADA | `01a9d8f` | `tests/test_puerto_notas_indexables.py` | unittest enumeración: 4/4 OK, exit 0; pytest de ambos ficheros de contrato: 10 passed | `root=self.otra` manda sobre el ambiente apuntando a `self.raiz`; sin contaminación, con filtros, orden estable y equivalencia con el criterio del dominio | `R1B-Q03-unittest.txt` |
| E04a saneamiento de evidencias | COMPLETADA | `5c27601` | `audits/handoff/logs/2026-10-24-Q00-baseline.md` | `pytest tests/test_publicacion_limpia.py`: 6 passed, exit 0 | ruta local del autor sustituida por marcador neutro; se conserva SO, terminal, Python y forma de la ruta | `R1B-E04a-saneamiento.txt` |
| E04b fixtures arquitectónicos | COMPLETADA | `031abfb` | `tests/test_puente_sin_hogar.py`, `tests/test_puertos_verificados.py` | pytest de ambos ficheros: 167 passed, exit 0 | los cuatro tests usaban como ejemplo símbolos publicados como puertos en la ronda 1; reencaminados preservando su capacidad de detección, demostrada con par positivo/negativo (al retirar el puerto, el cruce reaparece con su clave exacta) | `R1B-E04b-fixtures.txt` |
| E04c corrección H4 | COMPLETADA | `2eabcfe` | `README.md`, `tests/test_quickstart_del_readme.py` | test afectado: 2 passed, exit 0 (antes: `ValueError: No closing quotation`, exit 1 en f3aaafc); regresión relacionada: 44 passed | defecto PREEXISTENTE reproducido en f3aaafc en worktree aislado; portados SOLO los dos hunks del commit local de main `0a06696` (no publicado en GitHub — anotado para QA); sin cambios de producto | `R1B-E04c-h4.txt` |
| E04e CI | COMPLETADA (actualización final tras el push de este informe) | `bc741dc` + cierre | `audits/handoff/logs/R1B-E04e-ci.txt` | consulta `gh run list` + API de jobs | 13 runs de la rama en cola, 1 en curso (SHA de QA), 4 completados con fallo en SHAs PREVIOS a la rama; yaml = job de wheel, JSON-RPC = tests que miran historial git truncado en CI; clasificación: preexistentes; dictamen CI: PENDIENTE DE VALIDACIÓN | `R1B-E04e-ci.txt` |
| E04d validación integral | COMPLETADA | `988f5b7` | logs bajo `audits/handoff/logs/` (11 ficheros) | ver sección Validación | suite 1 failed/6140 passed/11 skipped (el 1 era higiene de la propia evidencia, corregido y reverificado 6/6); puertas 24/26 con las dos causas documentadas | `R1B-E04d-validacion.txt` |
| E05 informe | COMPLETADA | este commit | `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` | — | este documento | — |

## Validación (entorno aislado: worktree dedicado en `2eabcfe`, sandbox propio inicializado con la herramienta de la rama `vault_standard_upgrade --to v41.23`, v20→v41.23 con migraciones; sin editar `applied_version`; sin tocar el sandbox compartido)

| Verificación | Comando | Exit | Resultado |
|---|---|---|---|
| Entorno | `python --version` | 0 | Python 3.14.3 |
| AP-39 | `python -m unittest discover -s tests -p "test_ap39_contrato.py"` | 0 | Ran 6 tests in 15.276s — OK |
| Enumeración | `python -m unittest discover -s tests -p "test_puerto_notas_indexables.py"` | 0 | Ran 4 tests in 24.399s — OK |
| Arquitectura estricta | `python scripts/vault_arch.py --check --strict` | 0 | ok: true; `new_off_port_crossings: []`; `off_port_total: 5`; `off_port_baseline: 5`; `broken_ports: []` |
| Gobernanza | `python scripts/vault_gate.py --strict` | 1 | **26 puertas: 24 pasan, 2 fallan** (ver Incidencias) |
| Suite integral | `python -m pytest tests/ -q -n auto --tb=short` | 1 → corregido | 1 failed, 6140 passed, 11 skipped en 1405.85s; el único fallo era una ruta local en DOS LOGS PROPIOS de esta ronda, corregida y reverificada (`test_publicacion_limpia`: 6 passed, exit 0) |
| GitHub Actions | `gh run list --branch audit/... --limit 30` | 0 | 13 runs de la rama en cola (ninguno ejecutado); 4 completados con fallo en SHAs previos a la rama; **CI: PENDIENTE DE VALIDACIÓN** |

Condiciones innegociables de arquitectura: **cumplidas** (`new_off_port_crossings == []`, `off_port_total == 5 <= 5`, `off_port_baseline == 5`, baseline sin tocar — 5 entradas D–H, ni una más).

Aislamiento demostrado: del sandbox compartido solo cambiaron `.tool-trace.json` (21:46, ANTES de la corrida aislada) y `.voice-counter` (22:16, incremento del propio ejecutor al correr la comparación del noop en el checkout principal); la corrida aislada escribió únicamente en el sandbox del worktree. Recuento de ficheros idéntico: 131 antes y después.

## Incidencias

**Fallos preexistentes (no introducidos por la rama):**
1. **H4** — el ejemplo `vault_write` del README estaba roto desde antes de la ronda (reproducido en `f3aaafc` en worktree aislado). Corregido en `2eabcfe` con autorización condicional del propietario. NOTA DE TRAZA: la corrección de `main` vive en el commit local `0a06696`, sin publicar en GitHub; QA no puede cotejarlo en el remoto hasta que se publique.
2. **Puerta `noop` (AP-37) en rojo sobre un sandbox v41.23 limpio** — el modo ejecutado corre los ejemplos documentados contra una copia del sandbox, y el ejemplo de `vault_frontmatter_completar` asume una nota que `vault_init` no crea. Mismo commit: exit 0 contra el sandbox del checkout principal (que conserva esa nota de corridas previas) y exit 1 contra el limpio. Clasificación: AMBIENTAL + PREEXISTENTE. Se deja en rojo documentado — no se fabricó estado para sacar verde.
3. **CI en cola** — 13 runs de la rama sin ejecutar por el límite de concurrencia de runners (el run en curso, de un SHA previo a la rama, sostiene la cola con 24 jobs). Los 4 runs completados con fallo son de SHAs anteriores a `f3aaafc`: `ModuleNotFoundError: No module named 'yaml'` en "Product gates (wheel)" y fallos de tests que miran el historial git en "Validate Vault Spec". Clasificación: PREEXISTENTES.

**Regresiones corregidas (introducidas y cerradas por esta ronda):**
1. Ruta local publicada en la evidencia de Q00 → saneada (`5c27601`); el propio guard la detectó y su test vuelve a estar en verde.
2. Cuatro fixtures que usaban como ejemplo símbolos publicados como puertos → reencaminados con capacidad de detección demostrada (`031abfb`).
3. Dos rutas residuales en los logs de esta misma ronda (citadas dentro del "ANTES" de E04a y en un traceback de E04c) → saneadas durante E04d; el único fallo de la suite aislada era eso, ya reverificado en verde.

**Bloqueos ambientales:** CI sin ejecutar (cola de runners); documentado, sin cancelaciones ni relanzamientos.

**Pendientes:** dictamen de QA sobre esta ronda; publicación del commit `0a06696` de `main` (para que H4 sea cotejable en remoto); Q04–Q07 siguen en ANÁLISIS, sin cambios de comportamiento.

## Evidencias (audits/handoff/logs/)

`R1B-E01-sincronizacion.txt` · `2026-10-24-R1-respuesta-ejecutor.md` (informe de ronda 1, preservado) · `R1B-Q02-unittest.txt` · `R1B-Q03-unittest.txt` · `R1B-E04a-saneamiento.txt` · `R1B-E04b-fixtures.txt` · `R1B-E04c-h4.txt` · `R1B-E04d-validacion.txt` · `R1B-suite.txt` · `R1B-gates.txt` · `R1B-arch-strict.txt` · `R1B-sandbox-init.txt` · `R1B-docstaleness-recheck2.txt` · `R1B-noop-recheck.txt` · `R1B-E04e-ci.txt` · `2026-10-24-Q00-baseline.md` (ronda 1, saneado)

## Solicitud formal

**¿Se solicita aceptación QA?: SÍ**

**Estado de aceptación: PENDIENTE DE QA.** No se declara aprobada la ronda ni la suite: la aceptación corresponde exclusivamente a QA. Decisiones que se dejan en manos de QA: (1) aceptación o no de la corrección H4 y su trazabilidad parcialmente local; (2) el dictamen sobre la puerta `noop` en entorno limpio (ambiental/preexistente) y si su arreglo entra en una ronda futura; (3) la asignación de Q04–Q07.


---

# CIERRE TÉCNICO DE LA RONDA 1B (actualización posterior al informe)

**SHA final: `559e204`** · commits del cierre: `f24a9b8` (fix AP-37), `a813094` (evidencias gates/arch/suite/entorno), `559e204` (anexo CI) y este commit.

## Hallazgos

### H-QA-01 — AP-37 / no-op silencioso — RESUELTO
- **Causa identificada:** el ejemplo completo de `vault_frontmatter_completar` (`--path 07_Knowledge/x.md --apply`) presupone una nota que `vault_init` no crea. En un banco v41.23 limpio la tool rehúsa con NOTE_NOT_FOUND, no escribe y la entrada quedaba `sin_escritura_sin_motivo`; en un sandbox con corridas previas escribía — la medida dependía del residuo.
- **Dónde estaba el defecto:** NO en la implementación ni en el contrato de AP-37, sino en la DECLARACIÓN DE PRECONDICIONES del ejemplo. El mecanismo determinista ya existía (`FICHEROS_DEL_EJEMPLO` en `scripts/vault_noop_audit.py`) y su propio comentario prometía «los dos sanadores» sin declarar el segundo.
- **Archivos modificados:** `scripts/vault_noop_audit.py` (+8 líneas).
- **Justificación:** declarar la precondición con la plantilla `nota` existente —que no trae `createdAt/updatedAt/cia_*/agent`, justo lo que el completador añade— de modo que el `--apply` escriba de verdad en banco limpio. No se convierte NOTE_NOT_FOUND en éxito: la tool AHORA ESCRIBE y el banco lo mide.
- **Evidencia anterior:** `R1B-CIERRE-AP37-antes.txt` (exit 1, tool en `sin_escritura_sin_motivo`).
- **Evidencia posterior:** `R1B-CIERRE-AP37-despues.txt` (exit 0, tool en `medidas` = escritura real).
- **Pruebas:** test afectado verde en banco limpio; tests específicos del auditor (`test_ap37_ejecutado` + `test_ejemplos_de_escritores`): 22 passed.
- **Estado:** RESUELTO sobre entorno limpio y reproducible. **Riesgo residual:** el modo ejecutado de AP-37 sigue siendo sensible al estado del sandbox en general (documentado); otros ejemplos pueden tener dependencias no declaradas que solo afloran en entornos limpios.

### H-QA-02 — doc_staleness — VERIFICADO EN AGREGADO
- La regeneración ya no se hizo a mano: se usó el **bootstrap canónico del propio repo** (`tests/sandbox_fixture.py --bootstrap`), que genera los 7 artefactos y los verifica.
- **Evidencia:** `R1B-CIERRE-gates.txt` — `gates_total: 26, passing: 26, failing: 0`, exit 0, 521.1s, sobre el mismo entorno y SHA que la suite.
- **Estado:** VERIFICADO. Sin riesgos residuales conocidos.

### H-QA-03 — Suite integral — CERO FALLOS
- **Comando:** `python -m pytest tests/ -q -n auto --tb=short` — exit 0.
- **Resultado:** **6141 passed, 0 failed, 11 skipped**, 2 warnings, 1019.94s. (6141 + 11 = 6152 = la cifra que publica el derivado de conteos.)
- **Evidencia:** `R1B-CIERRE-suite.txt`.
- **Estado:** CERO FALLOS sobre el SHA final, sin omisiones artificiales (11 skips = los históricos de la suite).

### H-QA-04 — Arquitectura y contratos — INVARIANTES INTACTOS
- `python scripts/vault_arch.py --check --strict` → exit 0; `broken_ports: []`; `new_off_port_crossings: []`; `off_port_total: 5`; `off_port_baseline: 5`.
- La corrección de AP-37 no toca fronteras, contratos ni propietarios: añade una precondición declarada de un ejemplo.
- **Evidencia:** `R1B-CIERRE-arch.txt`. **Estado:** INVARIANTES CONSERVADOS.

### H-QA-05 — Integración continua — PENDIENTE DE VALIDACIÓN EXTERNA
- Consulta fresca tras el push final: todos los runs de la rama (incluido el del fix AP-37 y el del cierre) siguen **en cola**; los 4 completados con fallo siguen siendo de SHAs anteriores a `f3aaafc` (preexistentes, investigados en `R1B-E04e-ci.txt`).
- **Evidencia:** `R1B-CIERRE-ci.txt`. **Estado:** CI: PENDIENTE DE VALIDACIÓN EXTERNA. No se atribuye aprobación de CI a los resultados locales.

## Resultados

```text
AP-37:             PASA EN SANDBOX LIMPIO (fix publicado, par antes/después con escritura real)
QUALITY GATES:     26/26, exit 0 (521.1s)
ARCHITECTURE:      exit 0; broken_ports [], new [], total 5, baseline 5
FULL TEST SUITE:   6141 passed, 0 failed, 11 skipped, exit 0 (1019.94s)
GITHUB ACTIONS:    PENDIENTE DE VALIDACIÓN EXTERNA (todo en cola; fallos observados preexistentes)
MAIN:              INTACTO (local 4efcf22, origen 1c34754; ningún push a main)
ISOLATED BRANCH:   audit/archify-governance-20261024 @ 559e204, publicada
```

## Incidente documentado del cierre (transparencia)

La validación requirió cuatro pasadas. Las tres primeras fallaron por el ENTORNO, no por el código: (1) la reconstrucción borró el `tool-spec.json` VERSIONADO —el bootstrap de la suite lanzó INTERNALERROR y cinco puertas cayeron en cascada—; (2) restaurarlo con `vault_manifest --bootstrap` generó una spec de introspección (159 activas) en lugar del contrato curado —los tests de campos la rechazaron con razón—; (3) fijar `VAULT_ROOT` rompió los tests que ejercitan la detección, y el orden gates-antes-de-suite sobre un sandbox no-ready hizo que la suite lo reconstruyera y limpiara. La pasada 4 usó el procedimiento canónico del propio repo (`tests/sandbox_fixture.py --bootstrap`) y dio verde completo. Detalle completo: `R1B-CIERRE-entorno.md`.

## Dictamen solicitado

Se solicita a QA una de: **ACEPTADO / ACEPTADO CON OBSERVACIONES / REQUIERE CORRECCIONES / BLOQUEADO**, sobre las evidencias de este cierre. La CI permanece como validación independiente pendiente; su estado no invalida ni aprueba el cierre local documentado.


---

# ACUSE DE RECIBO — dictamen de cierre técnico (2026-10-25)

- **Dictamen leído:** `audits/handoff/RESPUESTA-QA.md` en el commit `d78604a` de `origin/audit/archify-governance-20261024` (sincronizado por fast-forward; árbol limpio).
- **Dictamen:** ACEPTADO CON OBSERVACIONES — cierre técnico LOCAL de ronda 1B.
- **Registro del ejecutor:** H-QA-01 a H-QA-04 aceptados en alcance local; H-QA-05 (CI) PENDIENTE. La observación de QA sobre la trazabilidad de los tres intentos fallidos se conserva tal cual: es parte del valor del registro.
- **Vigilancia activa del ejecutor:** cuando CI tenga capacidad de ejecutar los runs de la rama, se documentará estado, matriz multiplataforma, dependencias de wheel (incluido PyYAML) y pruebas JSON-RPC antes de cualquier solicitud de autorización de distribución.
- **Sin acciones iniciadas:** ni merge de PR #1 a `main`, ni Q04–Q07, ni release — todas requieren decisión explícita del propietario.

**Estado de la ronda 1B: CERRADA EN ALCANCE LOCAL, a la espera de las decisiones del propietario.**

---

# FASE 2 — Deuda tecnica, Quality Gates y Product Readiness · LOTE L1 (2026-10-25)

- **Rama de fase 2:** `fase2/deuda-y-product-readiness-20261025`, derivada de `ef77a7b` (punta de la rama auditada, con el acuse del dictamen).
- **Rama auditada de ronda 1B:** `audit/archify-governance-20261024` — **congelada**, sin commits nuevos. `main` intacta (local `4efcf22`, origen `1c34754`).
- **SHA base del descubrimiento:** `ef77a7b19a6aaa5e8a5bf776181ab887b7ee4587` · Python 3.14.3 · Windows/PowerShell 5.
- **Alcance de L1:** inventario de los diez contextos y reconciliacion del snapshot de Archify con el codigo actual. **No se ha modificado codigo de producto** (las herramientas de `audits/fase2/` son de auditoria, no del producto).

## Resultados de L1

| Comprobacion | Resultado |
|---|---|
| Contextos inventariados | **10/10**, con puertos, modulos y prohibiciones desde el registro vivo (68 puertos en total) |
| Pares de cruce del presupuesto | **23/23 coinciden con el registro y con ficha IDENTICA** (objetivo, dueno, revisado, cadencia, por que): cero divergencias |
| Dependencias del snapshot (37, a nivel de fichero) | Colapsan a **23 pares de contexto, los 23 vigentes**: reconciliacion completa |
| Accesos fuera de puerto del snapshot (8) | **5 vigentes** (los de Q04–Q07, con su cruce y su simbolo) y **3 resueltos en ronda 1** con su commit (Q01/Q03) |
| Anclas del puente | **2/2** coinciden, con motivos identicos |
| Delta total contra el snapshot | `indices` con 3 puertos mas (los publicados en ronda 1) y `meta_toolkit` con 1 modulo mas |

**Instrumentos creados (reproducibles):** `audits/fase2/reconciliar_archify.py` (confronta snapshot y codigo) y `audits/fase2/matriz_contextos.py` (genera la matriz desde el registro). Evidencia: `audits/fase2/logs/L1-reconciliacion-archify.txt` y `.json`.

## Hallazgos (6; registro canonico en `audits/fase2/inventario-deuda.yaml`)

| ID | Sev | Hallazgo | Estado |
|---|---|---|---|
| TD-0001 | **P1** | El job de CI de la wheel ejecuta las puertas del producto sin instalar el paquete → `ModuleNotFoundError: 'yaml'` → ese job no puede pasar nunca; el defecto esta en el workflow, no en los metadatos (PyYAML SI esta declarado) | vigente |
| TD-0003 | **P1** | Un control que no puede cargar su dependencia (3 bloques `except → pass` en `vault_norms_engine.py:151,179,196`) informa cero hallazgos: la ausencia de hallazgos no significa ejecucion | vigente |
| TD-0002 | P2 | Las trazas runtime del servidor MCP (958 KB) caen dentro del paquete mapeado `vault_toolkit.mcp` y `exclude-package-data` no las cubre | no verificada (se mide en L3) |
| TD-0005 | P2 | Seis documentos de producto (2 PRD, contrato de runtime, instalacion limpia, `gaps.md`, `PUERTAS.md`) sin clasificar | no verificada (L4) |
| TD-0006 | P2 | Las baselines estan por encima de su objetivo declarado con plazo activo: `off_port_crossings` 5 vs objetivo 4; `crossings` 37 vs objetivo 30; ambos con `fecha_limite: 2027-03-31`. El mecanismo mide que no crecen, no la aproximacion | vigente |
| TD-0004 | P2 | Reconciliacion del snapshot de Archify | **corregida** (instrumento ejecutable y repetible) |

**P0: ninguno** con la evidencia reunida. El recorrido MVP de L3 puede cambiarlo; si apareciera perdida de datos o corrupcion del runtime, se avisa de inmediato.

## Un hallazgo que condiciona L2

Las dos fichas de cruce con `objetivo: a_eliminar` y `fecha_limite: 2027-06-30` nombran **exactamente** los modulos de Q04–Q07:

- `gobernanza → meta_toolkit`: «`vault_norms_engine` importa `vault_smoke` y `vault_mcp_catalog` en diferido para auditar el catalogo» → **Q04 + Q05**
- `gobernanza → autoria`: «`vault_norms_engine` -> `vault_voice`: presentacion colgada del motor» → **Q06**

O sea: Q04–Q07 **no son deuda desconocida**; el repo decidio el 2026-08-14 eliminarlos (no formalizarlos como puertos), con plazo. L2 investiga el COMO (inversion, adaptador o contrato), con las tres pruebas exigidas, sin implementar.

## CI: PENDIENTE DE VALIDACION EXTERNA (documentado, sin cancelar)

| Run ID | SHA | Estado | Conclusion | Clasificacion |
|---|---|---|---|---|
| 40168004595 | `a813094` | queued | — | PENDIENTE (cola de runners) |
| 40161384740 | `f24a9b8` | queued | — | PENDIENTE |
| 40159084620 | `bcc1f8b` | queued | — | PENDIENTE |
| 40147533176 | `8885c79` | completed | failure | **PREEXISTENTE**: 24/25 jobs en rojo; `yaml` ausente en «Product gates (wheel)» y fallos de tests que miran el historial git truncado en el checkout de CI |
| 40147250440 / 40147115820 / 40147025723 | `3adc050` / `08a2ddf` / `40d81e6` | completed | failure | **PREEXISTENTES**, SHAs anteriores a `f3aaafc` |

**Causa conocida:** limite de concurrencia de runners; un run antiguo (`069616a`, de un commit de QA de la ronda 1) sigue en curso y sostiene la cola. **No se cancela ninguna ejecucion** (condicion 2 de la orden). **Causa pendiente de investigacion:** por que el job de la wheel no instala el paquete (TD-0001) — su evidencia local llega en L3. La CI pendiente no impide investigar, pero **impide aprobar un release estable**.

## Riesgos y bloqueos

1. **La comparacion CLI↔MCP y el recorrido MVP son el unico punto que puede abrir un P0** (instalacion limpia, persistencia, contencion). Se ejecutan en L3 con la wheel construida y un venv nuevo fuera del checkout.
2. **El metodo de comparacion tiene una asimetria conocida:** el lado MCP es un `.mjs` de 97 KB con su propio catalogo, y el lado CLI un registro de operaciones en Python. La paridad se medira sobre resultados NORMALIZADOS, no sobre igualdad literal de respuestas de transporte.
3. **La deuda de documentacion (TD-0005) puede contener hallazgos ya corregidos:** `docs/sdd/gaps.md` es un historico y se reconciliara antes de contarlo (L4).
4. **Ningun hallazgo se ha cerrado sin evidencia:** TD-0002 y TD-0005 siguen como `no_verificada` hasta que L3/L4 las midan.

## Siguientes acciones

1. Revision tecnica de este L1 por QA (el buzon de QA sigue siendo suyo).
2. Con el visto: **L2** (investigacion de Q04–Q07 con causa, contrato, decision y tres pruebas por control).
3. En paralelo, **L3** (wheel + venv + paridad CLI/MCP + recorrido MVP) y **L4** (documental + seguridad + reconciliacion historica).
4. Decisiones que se piden al propietario y QA: corregir TD-0001 (workflow) cuando L3 lo demuestre; autorizar o no la implementacion de TD-0003 cuando L2 traiga el diseno; fijar la prioridad entre deuda de entrega y preparacion de producto.

**Estado de la fase 2: PLANIFICACION EN CURSO. No se declara aprobada ni el producto.**

---

# FASE 2 — LOTE L3 (2026-10-25): VIAJE REAL DE DISTRIBUCION

- **Rama:** `fase2/deuda-y-product-readiness-20261025` · **SHA base:** `ef77a7b` (derivada de la rama auditada, congelada).
- **Entorno:** Windows 11, Python 3.14.3, Node 24.14.0, red disponible (PyPI accesible).
- **Artefacto:** `vault_obsidian_architecture-41.23-py3-none-any.whl` (1.661.092 bytes, 705 miembros), construido con la tool de la rama y con el interprete que REPLICA el job de CI (solo `build` instalado).
- **Alcance:** TD-0001 (correccion autorizada), TD-0002 (verificacion), recorrido MVP y paridad CLI<->MCP. **Sin codigo de producto modificado** (unica excepcion: el workflow de CI).

## 1. TD-0001 — causa raiz, correccion y verificacion

**Causa raiz (confirmada y reproducida):** `tests/clean_install_gate.py` importa el paquete (`vault.meta_toolkit.distribucion` -> `frontmatter_parsing` -> `import yaml`) en el **interprete del runner**, y el job de la wheel solo instalaba `build`: la dependencia PyYAML, **declarada** en `pyproject.toml`, nunca llegaba a estar. El gate moría antes de medir.

**Correccion (minima, cross-platform):** paso nuevo `Install wheel (artefacto y dependencias declaradas)` antes de `Run product gates`, con `shell: bash` —el mismo shell que ya usa el paso de SBOM de ese job— para que el glob de la wheel se expanda igual en los tres sistemas. No se tocan producto, tests ni cobertura.

| Momento | Entorno | Resultado |
|---|---|---|
| Antes | venv 'runner' (solo `build`) | `clean_install: FAIL` — `ModuleNotFoundError: No module named 'yaml'` (clean_install_gate.py:48) |
| Despues | el mismo venv + `pip install dist/*.whl` | `clean_install: PASS`, `memory_e2e: PASS`, **Overall: ALL PASS**, exit 0 |

Evidencia: `audits/fase2/logs/L3-TD0001-antes.txt` y `L3-TD0001-despues.txt`.

**Pendiente:** el run de CI del SHA corregido (la rama de fase 2 necesita un PR para que dispare el evento `pull_request`: decision del propietario). Por eso TD-0001 queda en estado **parcial**: la correccion esta aplicada y verificada en local, la confirmacion de CI no existe.

## 2. TD-0002 — hipotesis refutada

La wheel **no lleva trazas runtime**: 0 trazas entre 705 miembros, tanto construida desde el checkout como desde una copia limpia sin `.git` (ambas dan 1.661.092 bytes, 4 ficheros en `vault_toolkit/mcp/`). El motivo es **declarativo**: `[tool.setuptools.package-data]` nombra para `vault_toolkit.mcp` exactamente los cuatro ficheros que deben viajar. **Estado: falso positivo** (no aplica). Evidencia: `audits/fase2/logs/L3-wheel-contenido.txt`.

## 3. Recorrido MVP — 16/16, desde el artefacto y fuera del checkout

Ejecutado de verdad (`audits/fase2/recorrido_mvp.py`, reejecutable):

| # | Paso | Resultado |
|---|---|---|
| 1 | venv nuevo FUERA del checkout | OK |
| 2 | wheel instalada en ese venv | OK |
| 3 | script de consola `vault` instalado | OK |
| 4 | runtime externo creado con `vault init` | OK |
| 5 | nota escrita por CLI (`vault run vault_write`) | OK |
| 6 | servidor MCP **del artefacto** (`vault_toolkit/mcp/…`) presente | OK |
| 7 | handshake MCP (`initialize` -> `notifications/initialized`) | OK (protocolo 2024-11-05) |
| 8 | `tools/list` | OK — **97 tools** expuestas |
| 9 | leer la nota por MCP (`vault_read`) | OK |
| 10 | modificarla por MCP (`vault_write`) | OK |
| 11 | consultarla por MCP (`vault_search`) | OK |
| 12 | **persistencia tras reiniciar el proceso MCP** (proceso nuevo) | OK — la linea escrita por MCP sobrevive |
| 13 | verificar por CLI el cambio hecho por MCP | OK |
| 14 | **contencion**: intento de escritura fuera de la raiz | OK — **rechazado**, no se escribio fuera del runtime |
| 15 | la nota existe en disco dentro del runtime | OK |
| 16 | `vault status` ve el runtime sano | OK (exit 0) |

Evidencia: `audits/fase2/logs/L3-recorrido-mvp.txt`.

**Dos desviaciones fueron mias y las corrigio el instrumento, no el producto:** el primer intento escribio por CLI un cuerpo de 2 lineas y el gate **AP-11** lo rechazo con exit 7 (correcto: el gate exige tres; el write por MCP, con tres, paso); y mi criterio de "lectura correcta" miraba la ausencia de una palabra que el frontmatter lleva. Ninguna de las dos era un defecto del producto.

## 4. Paridad CLI <-> MCP — 5/5, con el verificador de contrato en verde

Medida sobre el **mismo runtime**, con fotografia y restauracion del estado entre adaptadores (sin eso, la segunda llamada de una escritura mide un update donde la otra midio un create: divergencia del guion, no del producto).

| Operacion | CLI | MCP | Coincide |
|---|---|---|---|
| `vault_read` (inexistente) | `ok:false` | `ok:false` | si |
| `vault_search` | `ok:true, total:0` | `ok:true, total:0` | si |
| `vault_list` | `ok:true` | `ok:true` | si |
| `vault_write` (crea) | `ok:true, created:true` | `ok:true, created:true` | si |
| `vault_write` (actualiza) | `ok:true, updated:6` | `ok:true, updated:6` | si |

**Nivel de contrato:** `vault_mcp_catalog --check-params` (el verificador AP-40 del repo, el mismo que corre en CI) → **exit 0**: el esquema MCP y el argparse de cada tool concuerdan.

Matriz: `audits/fase2/matriz-paridad-cli-mcp.md` · Log: `audits/fase2/logs/L3-paridad-cli-mcp.txt`.

## 5. Limitaciones de L3 (lo que NO se ha medido)

1. **Multiplataforma y versiones:** todo esto es Windows + Python 3.14.3 + Node 24. La matriz declarada (ubuntu/macos, Python 3.9-3.12) solo la ejecuta la CI, y la CI esta en cola: **no hay veredicto multiplataforma**.
2. **Seguridad completa:** L3 cubre contencion (traversal rechazado) y aislamiento (origen en `site-packages`, checkout no importable — lo afirma la puerta `memory_e2e`). El barrido de seguridad (secretos, superficie del transporte MCP, dependencias, cadena de suministro) es de L4.
3. **Cobertura de la paridad:** 5 operaciones medidas sobre 97 tools expuestas. La paridad del resto no esta medida; el verificador de contrato (AP-40) si cubre todas las tools.
4. **Q04–Q07:** sin tocar (investigacion autorizada para L2, implementacion pendiente de dictamen).
5. **P0: ninguno** detectado en el viaje real: no hubo perdida de datos, ni corrupcion del runtime, ni escritura fuera de la raiz.

## 6. Riesgos y bloqueos

1. **CI en cola** → TD-0001 queda parcial y QG-07 no puede cerrarse. No se cancela ninguna ejecucion.
2. **La rama de fase 2 no tiene PR** → el workflow (eventos `push` a main/master y `pull_request` a main/master) no se dispara para ella. Decision del propietario: abrir un PR de la rama de fase 2.
3. **La paridad medida es una muestra**: 5 operaciones de 97. QG-05 debe declarar ese alcance (muestra + verificador de contrato) o exigir cobertura total.
4. **Observaciones, no hallazgos:** `vault status` exige el argumento `runtime` mientras `vault init` no lo pide (ergonomia, exit 2 de uso); el gate AP-11 rechazo correctamente un cuerpo de dos lineas — el gate de contenido funciona en el artefacto instalado.

## 7. Siguientes acciones

1. Revision tecnica de L3 por QA (su buzon sigue siendo suyo) y decision sobre el PR de la rama de fase 2.
2. Con el visto: **L4** (documental, seguridad e historia) o **L2** (Q04–Q07, solo investigacion), segun la prioridad que fije el propietario.
3. Cerrar TD-0001 cuando exista un run de CI con conclusion sobre el SHA corregido.

**Estado de la fase 2: PLANIFICACION Y DIAGNOSTICO EN CURSO. No se declara aprobada la fase ni el producto.**

---

# FASE 2 — L3 (correcciones) y L2 (investigacion) · 2026-10-25

- **Rama:** `fase2/deuda-y-product-readiness-20261025` · **SHA base:** `ef77a7b` (rama auditada, congelada) · **Entorno:** Windows 11, Python 3.14.3, Node 24.14.0.
- **Alcance de este tramo:** las tres correcciones que QA pidio sobre L3, la apertura del PR autorizado y la investigacion de L2 (Q04–Q07). **Sin implementar** Q04–Q07.

## 1. Correcciones de L3 (una por commit, con prueba y evidencia)

| Correccion | Commit | Que se hizo | Evidencia | Prueba |
|---|---|---|---|---|
| **H-L3-01** saneamiento | `bc1a1e6` | Tres logs estaban en **UTF-16 sin BOM** (3859/3184/1186 bytes NUL) y varios conservaban la estructura de la maquina detras del marcador. Todo a UTF-8 y toda ruta absoluta a `<RUTA-LOCAL>`. Se anade `audits/fase2/comprobar_saneamiento.py` (ejecutable) + `tests/test_fase2_logs_saneados.py` | `H-L3-01-saneamiento.txt` | Antes: **13 problemas, exit 1**. Despues: **conforme, exit 0**. Test: 8 passed (2 nuevos + los 6 del guard del repo) |
| **H-L3-02** paridad fail-closed | `d657fb0` | La evaluacion vive en `evaluar()` (funcion PURA): falla si AP-40 no sale 0, falta un campo obligatorio, divergen codigos o significado del error, divergen los efectos, un caso requerido no se ejecuto, o llega `isError`/`error de transporte` que contradice al otro adaptador | `H-L3-02-paridad-fail-closed.txt` | **11 tests** (control positivo + 10 negativos). Real: 5/5, AP-40 exit 0, 97 tools, **CONFORME** |
| **H-L3-03** timeout del harness | `44a880e` | `readline()` bloqueante -> hilo + `queue.get(timeout=...)`. El cliente acepta el comando, lo que permite probar el silencio. Registrado como **TD-0007 (instrumento, P3, corregida)**: NO es un defecto demostrado del servidor MCP. Ademas los scripts de auditoria **sanean su propia salida** (el verificador los habia cazado) | `H-L3-03-timeout-mcp.txt` | Servidor mudo -> error de timeout en ~2s (con la version antigua se colgaba). Con MCP instalado: **2 passed** |

**Exposicion historica (investigada, sin reescribir historia):** `git grep` sobre `origin/main`, `origin/audit/…` y `origin/fase2/…` → **0 ficheros** con ruta local real, con el nombre del autor o con forma de credencial. No hay nada que contener ni rotar, y no se hizo force-push ni se reescribio historia: el estado de la ronda 1B se integro con un **merge** de los commits de QA (`1eca182`, `4f6170f`).

## 2. PR en borrador (autorizado)

**PR #2** — `fase2/deuda-y-product-readiness-20261024` → `main`: **DRAFT**, OPEN, MERGEABLE, **sin auto-merge**, sin merge de PR #1. El cuerpo identifica expresamente **los cambios heredados de la ronda 1B** (10 commits, dictamen `d78604a` "ACEPTADO CON OBSERVACIONES") y lo que añade esta rama. Al abrirlo se disparo el evento `pull_request`: **run `40173539210`** para el SHA de la rama.

## 3. L2 — investigacion de Q04–Q07 (TD-0003), sin implementar

**Hecho OBSERVADO y medido:** los tres controles del estandar viven en `scripts/vault_norms_engine.py::_checks_estandar` (AP-40 lineas 141-152, AP-42 159-180, AP-43 186-197), cada uno con `except (ImportError, OSError, ValueError): pass`. La funcion **no devuelve nada**: su unico canal es `flag(...)`. El envelope (`vault/gobernanza/auditoria_runtime.py`) publica `ok: True` **hardcodeado**, `total_violations`, `by_norm` y `violations`, y **no tiene ningun campo que declare que controles se ejecutaron**.

**Demostracion reproducible** (`audits/fase2/demostrar_control_degradado.py`): con la dependencia sana el control aparece en `by_norm` con su hallazgo; con la dependencia rota **desaparece y el envelope no avisa**. Medido en las tres familias.

**Causa:** el contrato de salida no tiene estados de ejecucion; "no se pudo mirar" y "no se encontro nada" son la misma senal.

**Consumidores analizados:** la CLI `--audit --strict` decide **solo** por `total_violations` (lineas 584-594) → un control degradado baja el contador a 0 y la puerta sale con exit 0 (**LECTURA DE CODIGO**: no se pudo aislar el exit code en un vault sintetico, y asi se declara); la puerta de coherencia compara `by_norm` antes/despues y veria "sin cambios" si el control no se ejecuto en ninguno de los dos pases; y el puerto publicado `auditar_normas` hereda el defecto.

**Lo que el registro ya decidio (y acota la via):** los dos cruces que sostienen estos accesos estan declarados `objetivo: a_eliminar` con `fecha_limite: 2027-06-30` → la intencion es **eliminar**, no formalizar. Propuesta: **inversion + contrato de estados** (`ejecutado | degradado | fallido | no_ejecutado`, mas un campo hermano `completo` para no cambiar `ok`). Se descarta formalizar `check_params`/`load_baseline`/`coverage` como puertos: contradice la ficha vigente y deja el defecto vivo.

**Pruebas propuestas** (NO implementadas): positiva (control sano con estado `ejecutado`), negativa (envelope sin estados no conforme), dependencia fallida (el control se declara no ejecutado y la auditoria no se presenta como limpia), regresion de consumidores (la CLI con un control degradado sale con codigo distinto de cero) y equivalencia (envelope sano identico al actual mas `checks`).

Documento completo: `audits/fase2/L2-analisis-q04-q07.md` · Evidencia: `audits/fase2/logs/L2-control-degradado.json` · TD-0003 actualizada en el inventario.

## 4. Estado y limites

- **CI: PENDIENTE DE VALIDACION EXTERNA.** El PR #2 ha disparado el workflow para la rama; hasta que un run tenga conclusion **no se declara CI aprobada**, y **QG-07 sigue pendiente**. No se cancela ni relanza ninguna ejecucion.
- **Sin merger a `main`**, `main` intacto, PR #1 sin fusionar, ronda 1B cerrada.
- Alcance de la paridad: **cinco** casos de 97 tools expuestas (el contrato de todas lo cubre el verificador AP-40).
- Validacion local: Windows + Python 3.14.3 + Node 24; la matriz ubuntu/macos × 3.9–3.12 depende de la CI.
- El release **no** se declara listo: QG-07 y la validacion multiplataforma siguen pendientes.

**Estado de la fase 2: L1, L3 (con sus tres correcciones) y L2 (investigacion) entregados; L4 (documental, seguridad e historia) pendiente de autorizacion. La aceptacion corresponde a QA.**

---

# FASE 2 — CIERRE DE PENDIENTES Y QUALITY GATES (2026-10-25)

**SHA base:** `b680ac8` (dictamen QA de L2/L3) · **SHA final:** `8a852de` · **Árbol:** limpio · **`main`: intacto** (local `4efcf22`, origen `1c34754`) · **PR #2 en DRAFT sin fusionar** · **PR #1 sin fusionar**.

## C1 — Cierre de observaciones de L3

### H-L3-04 · Exposición histórica — RESUELTO CON INVENTARIO
Mi afirmación anterior («0 ficheros con ruta real en ninguna rama publicada») era una lectura del **árbol** de cada ref, no de la historia: QA la señaló bien y **era materialmente incorrecta para el historial**. El nuevo instrumento (`auditar_exposicion_historica.py`) recorre **todos** los commits alcanzables que tocaron las evidencias, extrae cada blob y lo clasifica **publicando solo huellas sha256** de los valores (correlacionables sin mostrarlos).
- **Inventario:** 20 commits con exposición en 9 ficheros; categorías: `ruta_local` 45 · `nombre_personal` 11 · `nul_utf16` 6 · **`forma_secreto` 0**.
- El commit que QA nombró (`44f6f89`) está en el inventario ✓.
- **Clasificación:** dato personal y de entorno; **sin credenciales** → no hay incidente que escalar ni nada que rotar.
- **Contención propuesta al propietario:** (a) documentar y asumir, o (b) reescritura de historia con `git filter-repo`/BFG **con autorización expresa** (y avisando de que GitHub puede conservar los blobs tocados, de modo que la reescritura no garantiza la retirada).
- **Prevención verificada:** el verificador de saneamiento (exit 0) + los scripts de auditoría que **sanean su propia salida** + la prueba negativa de que el verificador detecta ruta real, UTF-16 y clave.
Evidencia: `audits/fase2/logs/H-L3-04-exposicion-historica.{txt,json}` · commit `1888cf0`.

### H-L3-05 · Paridad con identidad por escenario — RESUELTO
- Cada caso lleva `case_id` propio (READ_MISSING, SEARCH_HITS, LIST_FOLDER, WRITE_CREATE, WRITE_UPDATE); el verificador exige ejecutar **cada id**, rechaza **duplicados** y **no previstos**.
- **Efectos reales medidos**: estado del runtime antes/después por pasada (creados, modificados, eliminados y huellas con contenido normalizado —timestamps y uuid enmascarados—), telemetría de la llamada excluida por diseño, restauración del estado entre adaptadores, y comprobación de que **no se modifica nada fuera del runtime**.
- **17 pruebas**: control positivo + los 7 negativos que exigía QA (caso omitido, duplicado, no previsto, AP-40 roto, campo ausente, errores divergentes, exit code contradictorio, efectos divergentes, huellas distintas, modificación fuera del runtime) + los previos adaptados.
Evidencia: `audits/fase2/logs/H-L3-05-paridad-escenarios.txt` · commit `78807ab`.

### H-L3-06 · Plazo global del cliente MCP — RESUELTO
Un único deadline monotónico gobierna la llamada; las líneas con otro id **no lo renuevan**. Pruebas: servidor silencioso (timeout en el plazo), respuesta válida, mensajes con otro id, **notificaciones continuas sin la respuesta esperada** (el caso adversarial: el goteo no alarga el plazo) y terminación del proceso. 4 passed + 1 skipped sin servidor; 5 passed con él. Evidencia: `audits/fase2/logs/H-L3-06-plazo-global.txt` · commit `1448c4d`.

## L4 — Auditoría documental, de seguridad y de deuda histórica

- **L4-A documental** (`inventario-documental.yaml`, 8 documentos clasificados): el Quick Start del README es **INCOMPLETO** (mezcla la superficie del checkout con la del producto instalado — DOC-0001); ARQUITECTURA.md, PUERTAS.md, INSTALACION-LIMPIA.md y los ADR **VIGENTES** (el primero byte a byte con su derivado); los PRD **NO_VERIFICADOS** (DOC-0006); `.archify/` vigente como evidencia auxiliar.
- **L4-B seguridad**: contención presente y usada (**103 ficheros** con `assert_within_vault`) y medida en el recorrido (el escape es rechazado); el MCP **exige initialize** (error −32002); **cero tools de gobernanza** en la superficie CLI/MCP (96 operaciones); la wheel declara `PyYAML>=6.0` y `Requires-Python >=3.9`; sin trazas runtime en el artefacto. Pendientes: auditoría de dependencias, symlinks/TOCTOU y validación de `params` contra el `inputSchema`.
- **L4-C histórica** (`gaps.md` de v36.0 → v41.23): H1 **CORREGIDA** (`vault_undo` existe); H2 **PARCIAL** (14/167 con `--dry-run`); K3/K4 **PARCIALES** (21 `slugify`, 14 `utcnow`); D3 **VIGENTE** → **TD-0008**; resto NO_VERIFICADO (quedan para un lote de reconciliación ampliada).
- **L4-D nueva deuda**: **TD-0008 (P1)** `vault_init --clean` destruye el runtime sin copia previa; **TD-0009 (P2)** el Quick Start del README no declara su supuesto; TD-0010 confirmada (TD-0006). **Descartados con motivo**: ARQUITECTURA desfasada (mi instrumento comparó contra otro derivado), trazas en la wheel (medido: 0), tools de gobernanza por MCP (medido: 0), credenciales publicadas (medido: 0).

## Quality Gates — catálogo formal propuesto

`audits/fase2/catalogo-qg.yaml`: QG-00..QG-07 con el contrato completo (id, name, version, purpose, owner, acceptance_authority, scope, checks, required_evidence, pass/fail_criteria, blocking_policy, timeout_policy, waiver_policy, results). Reutilizan: las 26 puertas (QG-02), `vault_arch`+catálogo+esquemas+reconciliador (QG-01), la suite+`memory_e2e`+recorrido MVP (QG-03), `comprobar_saneamiento`+guard de secretos+contención (QG-04), el verificador fail-closed de paridad+AP-40 (QG-05), `clean_install_gate`+contenido del artefacto (QG-06) y la decisión de release (QG-07). **Invariantes de gobernanza** incluidos (no-executado ≠ PASS, control degradado ≠ completo, resultado ≠ SHA distinto, baseline sin ampliar, waiver con propietario/motivo/vencimiento, release sin CI local-only, resultado histórico ≠ prueba actual, documentación ≠ capacidad sin comprobar).

## TD-0003 — Diseño final (sin implementar)

`audits/fase2/L2-diseno-final.md`: inventario completo de consumidores, inversión de dependencias (los duenos ejecutan sus controles y entregan el resultado; el motor lo colecciona), contrato aditivo de estados (`checks[]` con `ejecutado|degradado|fallido|no_ejecutado` + `completo`), fail-closed de CLI y puerta de coherencia, migración en tres fases revertibles con plan de rollback, siete tests propuestos y riesgos. La vía C (formalizar los cruces como puertos) se descarta: contradice las fichas `a_eliminar` con plazo. **No se ejecuta ningún commit de implementación sin autorización adicional.**

## CI — PENDIENTE DE VALIDACIÓN EXTERNA

Tres runs de la rama de fase 2 en `queued` (últimos SHAs 44a880e, 47f5beb, 73e9592, 1c788e3, 8a852de, bcbe6e8); los 4 completados con fallo siguen siendo de SHAs **previos** a la rama (preexistentes). Log: `audits/fase2/logs/CI-cierre.txt`. No se cancela ni relanza nada. **QG-07: BLOCKED.**

**Estado de la fase 2: L1, L2 (investigación), L3 con sus tres correcciones, L4 y QG formalizado entregados. La aceptación corresponde a QA.**