# Respuesta del ejecutor a QA — ronda 1B

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