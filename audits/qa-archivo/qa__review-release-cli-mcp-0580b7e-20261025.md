# Archivo: `qa/review-release-cli-mcp-0580b7e-20261025`

- Commit(s) sobre la rama de trabajo:
  - `5de279a500c2cb07c8b092f1953d88866aba9f0a` 2026-10-25 — docs(qa): dictamen RC 0580b7e y hallazgos de rollback, evidencias y arquitectura
- Base: `0580b7e07b96b3b610d7ce5122be1522ea53562e`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-0580b7e-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — GOAL Release CLI + MCP (2026-10-25)

**Objeto:** auditoría de entrega del release candidate del ejecutor, no aprobación de publicación.
**SHA candidato congelado:** `0580b7e07b96b3b610d7ce5122be1522ea53562e`  
**Rama del ejecutor:** `work/release-cli-mcp-20261025`  
**Rama separada de este dictamen:** `qa/review-release-cli-mcp-0580b7e-20261025` (para no modificar ni invalidar el SHA candidato).
**Método:** análisis independiente en GitHub de commits/diffs, contratos, `vault_init.py`, auditoría de normas, colector QG, pruebas, documentos y GitHub Actions. **QA NO ejecutó localmente la suite, la wheel ni los escenarios destructivos.**

## Dictamen

**ENTREGA TÉCNICA REAL Y TRAZABLE; NO APROBADA PARA MERGE A MAIN NI PARA RELEASE A TERCEROS.** Estado sugerido: `REQUIRES_FIXES_AND_EXTERNAL_VALIDATION`, no `APPROVED`.

**Verificado en el repositorio:** existen ocho commits sobre `84f7c298` que implementan estado de controles de auditoría, cuarentena de `--clean`, colector QG, pruebas y documentos; rama candidata en el SHA anunciado; `main` remoto continúa en `1c34754258441550139ce895e182ab219c93f9bb`; PR #1 y #2 abiertos sin fusionar; no hay PR de release ni GitHub Actions del SHA candidato.

**Evidencia aportada por el ejecutor (no reproducida por QA):** 26/26 puertas, 6250 passed / 13 skipped / 0 failed, wheel/sdist construidos, inicio CLI y MCP (97 tools publicadas), lectura/persistencia tras reiniciar, recuperación de backup; inspección y `pip-audit` local sobre el entorno declarado. El resultado es valioso **dentro de su alcance**, no equivale a certificación multiplataforma ni a cobertura de todas las tools.

## Hallazgos bloqueantes nuevos

### QA-RC-01 — P1: `vault_init --clean` no garantiza rollback en todos los fallos declarados

**Código:** `scripts/vault_init.py`, `_preparar_clean` y `vault_init` (alrededor de líneas 526–704 en el SHA candidato).

- `_preparar_clean()` se llama **fuera** del `try/except` de `vault_init()`. Si el mecanismo alternativo hace una copia verificada y comienza a borrar el original, un `unlink()` o `shutil.rmtree()` que falle a mitad del barrido produce una excepción **sin rollback automático**. La cuarentena puede permitir recuperación manual, pero no cumple la garantía publicada de resultado transaccional.
- `_vault_init_sin_clean()` tiene salidas de error **como diccionario** (p. ej. `INVALID_INPUT` ante `target_version` desconocida). Después de mover el vault a cuarentena, `vault_init()` solo hace rollback ante excepción; si recibe `{"ok": false}`, continúa y marca `clean.estado = "VERIFIED"` sin restaurar el runtime anterior. Esto es un defecto de integridad de estado (aunque la cuarentena sobreviva).
- La aserción en `tests/test_vault_init_clean.py::test_clean_exitoso_deja_cuarentena_verificada_y_contenido_intacto` termina con `or True`, anulando la comprobación sobre el directorio original.

**Acción requerida:** prevalidar destino/versión antes de renombrar, proteger toda la transacción y la vía de fallback; ante `ok=false` restaurar o producir un estado de recuperación explícito **sin VERIFIED**. No borrar un directorio de recuperación hasta validar la restauración; no suprimir errores críticos con `ignore_errors=True` sin comprobar postcondiciones. Añadir pruebas sobre directorios descartables para: versión inválida, retorno `ok=false`, error inducido tras el primer borrado de fallback, error de copia de `.locks`, fallo de restauración y recuperación manual comprobada. Corregir la aserción. **No probar con vaults reales.**

### QA-RC-02 — P1: colector QG puede acreditar resultados sin comprobar la prueba

**Código:** `audits/fase2/colector_qg.py`, `verificar_evidencia`, `estado_desde_evidencias`, `colectar`.

- `verificar_evidencia` considera válida una evidencia textual si contiene el SHA completo o sus **primeros siete caracteres**, sin parsear el resultado del verificador, el exit code ni el tipo esperado de evidencia. El propio test positivo escribe solo `SHA: ... / resultado` y espera `ok=true`.
- Con esa condición, `colectar` declara `PASS` para QG-00, 01, 02, 04, 05 y 06 sin ejecutar realmente sus verificadores ni comprobar un resultado estructurado satisfactorio. QG-02 además evalúa `control_ejecucion.completo`, pero no confronta `total_violations` ni comprueba que las 26 puertas se hayan ejecutado y aprobado.
- `sha_en_git` solo verifica **existencia** del SHA, no que el working tree corresponda exactamente a ese commit. `_procedencia_suite` acepta un recibo JSON declarativo sin comprobar huellas del XML, estado de checkout ni procedencia externa.
- `estado_ci` considera suficiente un run `success` del SHA sin inspeccionar identidad del workflow y todos los jobs requeridos de la matriz; un workflow parcial/excepcional no demuestra por sí solo toda la certificación declarada.

**Acción requerida:** diferenciar lector y ejecutor de evidencia; QG en PASS solo con resultados estructurados de sus verificadores, comandos/exit code, contenido/hashes y procedencia por SHA y árbol. Los jobs CI deben pertenecer al workflow esperado y matriz exigida, con todos los requisitos concluidos. Pruebas negativas: fichero con SHA pero verificación FALLIDA; `vault_gate` devuelve error; auditoría con controles completos pero violaciones; recibo JUnit sintético o manipulado; CI `success` de workflow ajeno/incompleto; working tree distinto al commit. **No dar PASS fabricando texto con un SHA.**

### QA-RC-03 — P1 contractual/arquitectónica: Q04–Q07 trasladadas, no eliminadas

**Código:** `scripts/arch-baseline.json` y `scripts/vault_norms.py`.

La baseline anterior contenía cinco `off_port_crossings` con origen `vault_norms_engine`; la nueva conserva **cinco** con origen `vault_norms` hacia los mismos módulos/símbolos (`vault_mcp_catalog.check_params`, tres de `vault_smoke`, `vault_voice.coverage`). La ruta empaquetada ya no importa dependencias excluidas y eso **sí es una mejora comprobable**, pero la deuda fuera de puerto continúa en el grafo.

**Acción requerida:** no declarar Q04–Q07 eliminadas. Demostrar una solución de composición/inversión que satisfaga el contrato de puertos del registro **sin desplazar la misma excepción al otro módulo**, o presentar una decisión arquitectónica explícita para diferir la eliminación con dueño/plazo/riesgo aceptado. No alterar la baseline para simular reducción; cualquier cambio a la baseline requiere reconciliación individual y pruebas de arquitectura. Aceptar la mejora de empaquetado como subobjetivo completado, no como cancelación de deuda.

### QA-RC-04 — QG-07 BLOQUEADO: CI del SHA y candidatos sin PR

**Verificado en GitHub:** al consultar `work/release-cli-mcp-20261025` no hay runs de Actions (`total_count=0`) para ese branch; solo PR #1 y PR #2 permanecen abiertos para las ramas antiguas. El workflow `.github/workflows/vault-ci.yml` dispara `pull_request` hacia `main/master` y `push` hacia `main/master`. La rama de fase 2 conserva runs `queued`.

**Acción requerida:** abrir PR **DRAFT** del candidato a `main` **solo para habilitar revisión y CI**, sin merge ni auto-merge. Al existir historial heredado, indicar PR #1/#2 acumulados y no cerrarlos hasta tener integración aprobada. Investigar cola sin asumir causa: `runner_id=0` y respuesta 404 de billing por falta de permiso **no prueban** por sí solos límite de gasto o restricción de cuenta. El propietario puede verificar ajustes de Actions/facturación; si el bloqueo es externo, mantener `QG-07 BLOCKED` y no publicar release.

## Pendientes complementarios, no sustituyen los bloqueantes

- **QA-RC-05 — P2 experiencia de terceros:** contrastar PRD CLI/MCP y contrato del runtime, corrección del classifier `Production/Stable`, actualización/desinstalación sin pérdida de datos, y recorrido adicional de `--clean` protegido desde la **wheel instalada**, no solo tests internos de `scripts/vault_init.py`. El recorrido MVP publicado mide principalmente init y backup/restore, no prueba el nuevo `--clean` instalado.
- **Evidencia RC:** el propio ejecutor declara QG-00..06 en `BLOCKED` por falta de recibos contemporáneos del SHA. Es una declaración correcta. No cambiar a PASS hasta corregir QA-RC-02, regenerar artefactos y validar su procedencia.
- **Privacidad histórica:** quedan blobs públicos con rutas/nombre personal; no se ha demostrado exposición de credenciales en el alcance auditado. La decisión de reescribir historia es exclusivamente del propietario; no hacer `force-push`, filtrar los nombres o borrar evidencia unilateralmente.
- **Main local divergente:** el ejecutor informa tres commits locales resguardados en `backup/main-local-4efcf22`; QA solo pudo verificar `origin/main`, no su worktree. Integración final debe preservar/reconciliar esos tres commits por su contenido antes de sincronizar la rama local.

## Decisión y condiciones de aceptación

**Aceptado como avance:** implementación y pruebas reportadas de TD-0003, aislamiento de la wheel, recorrido de consumidor, diseño/primer código de TD-0008 y organización de Git.

**No aceptados aún:** cierre funcional integral de TD-0008; cierre definitivo de Q04–Q07; colector de QG como acreditador de release; QG-00..07 del candidato; merge de PRs; release estable.

**Siguiente ronda autorizable por el propietario:** un lote acotado `QA-RC-01..05` con pruebas negativas primero, correcciones pequeñas, sin tocar datos reales, sin ampliar baselines y sin borrar referencias Git. Publicar commits/evidencia por unidad, congelar **nuevo** SHA candidato y solicitar nueva revisión QA. Abrir PR Draft para CI cuando proceda, pero nunca fusionar automáticamente.

**Resultado:** `QA_REQUIRES_CHANGES` para el candidato `0580b7e`. La rama de QA preserva el SHA del ejecutor y no modifica su artefacto, `main`, ni los PR abiertos.

