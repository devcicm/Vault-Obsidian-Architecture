# Archivo: `qa/review-release-cli-mcp-4396273-20261025`

- Commit(s) sobre la rama de trabajo:
  - `8dbd5b0d00509e7d5d9310f82c4f993962910117` 2026-10-25 — docs(qa): dictamen intermedio 4396273, fallos residuales de recuperacion y ruta a cierre
- Base: `4396273ea24232fc3de1838a57551ccb23a3a4ba`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-4396273-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — ronda intermedia QA-RC-01 (2026-10-25)

**Candidato de trabajo:** `4396273ea24232fc3de1838a57551ccb23a3a4ba`  
**Rama de ejecución:** `work/release-cli-mcp-20261025`  
**Rama exclusiva de revisión:** `qa/review-release-cli-mcp-4396273-20261025`; no se modifica el SHA del ejecutor.  
**Dictamen previo de referencia:** `5de279a500c2cb07c8b092f1953d88866aba9f0a` (rama QA del RC anterior).
**Método:** revisión independiente del diff y del código publicado, pruebas estáticas y estado de PR/Actions. **QA no volvió a ejecutar las pruebas locales**.

## Decisión

**QA-RC-01: PARCIALMENTE CORREGIDO, NO CERRADO.** La entrega de un commit y pruebas focalizadas es válida como avance, pero todavía hay caminos de integridad y garantías de restauración incompletos. **No aceptar `TD-0008=CERRADO`**, no fusionar ni publicar como release.

### Avances verificados

- En la vía de fallback (rename imposible), un `OSError` durante el borrado ahora produce intento de restauración con `_restaurar_copia` o estado `RECUPERACION_PENDIENTE` conservando la cuarentena.
- `vault_init()` trata un resultado de inicialización `ok: false` como error y solicita recuperación.
- Se eliminó la aserción `or True` del test de limpieza.
- Hay tres nuevos casos de prueba visibles en el diff, incluidos versión inválida y restauración fallida; el ejecutor reporta `16 passed / 1 skipped` en los 17 casos del módulo.

### Incidencias aún abiertas

**QA-RC-01a — P1: estado ROLLBACK comunicado falsamente si la recuperación falla.** En los dos caminos de `vault_init` (excepción en `_vault_init_sin_clean` y resultado `ok: false`) se asigna `clean.estado = "ROLLBACK"` **sin comprobar** `restauracion["ok"]`. Si `_restaurar` falla, debe publicarse `RECUPERACION_PENDIENTE` con ruta de la cuarentena y error seguro, nunca un estado de rollback completado. Pruebas negativas para ambos caminos.

**QA-RC-01b — P1: excepción durante preparación tras mover el vault puede dejarlo en cuarentena sin ruta/rollback.** El `try` exterior ahora captura `BaseException` de `_preparar_clean`, pero solo devuelve `cuarentena: None` y `RECUPERACION_PENDIENTE`; **no intenta restaurar** ni conoce qué fase se alcanzó. Por ejemplo, tras un `raiz.rename(cuarentena)` exitoso, si `raiz.mkdir` o la copia de `.locks` fallan, el vault original queda movido. La transacción debe gestionar sus propios estados y tener acceso a la cuarentena real incluso en esas fallas. Preferir transiciones explícitas y recovery conservativo; probar fallos inducidos en `mkdir` y `.locks`. No realizar borrado de datos reales.

**QA-RC-01c — P1: rollback desde copia no verifica la integridad restaurada.** `_restaurar_copia` hace `shutil.copytree(..., dirs_exist_ok=True)` y reporta `ok: true` sin re-inventariar ni verificar hashes del original. Debe comprobar igualdad de estado observable y tratar parcialidad/corrupción como `RECUPERACION_PENDIENTE`. Usar inventario previamente calculado, sin asumir que una copia sin excepción equivale a recuperación acreditada.

**QA-RC-01d — P2: prueba de borrado parcial no induce borrado parcial real.** El test parchea `shutil.rmtree` para lanzar siempre antes del primer borrado exitoso. El assert de igualdad del estado original puede pasar sin restauración efectiva. Inyectar el fallo **después** de eliminar al menos una entrada o fichero, documentar la prueba y verificar los hashes tras rollback. No alterar archivos de usuarios.

**QA-RC-01e — P2: no ampliar estado de aceptación por un test skipped.** La prueba de symlink se omitió por falta de privilegios. Es razonable registrar skip de entorno, pero no sustituye la prueba de protección de symlinks en una plataforma donde sí puedan crearse.

## Estado de las otras unidades y CI

- **QA-RC-02** (`colector_qg.py`): sin cambios; continúa pendiente, con riesgo de PASS por mención textual de SHA.
- **QA-RC-03** (5 cruces off-port): sin cambios; siguen presentes en baseline bajo `vault_norms`.
- **QA-RC-04**: PR #3 **DRAFT/OPEN**, head `4396273`, sin merge, base `main`; run `40231757273` permanece `queued` sin conclusión al consultar. La causa concreta de cola no está demostrada solo con billing 404.
- **QA-RC-05** (recorrido desde wheel instalada con `--clean`): sin ejecutar para este SHA, pendiente.
- **QG-00 a QG-07**: sin acreditación contemporánea; el propio ejecutor los declara `BLOCKED`. No hay veredicto de suite y 26 puertas para el nuevo SHA.

## Directiva de continuidad y criterios de cierre

Este es un **dictamen intermedio**, no reinicia la auditoría total. Las tareas anteriores están **dentro del GOAL previamente autorizado**: el agente debe continuar automáticamente corrigiendo los pendientes de QA-RC-01 y después QA-RC-02/03/05, con commits/evidencia por causa, sin detenerse a pedir permiso ni esperar a que la CI en cola resuelva su bloqueo externo.

Al final: cerrar rutas de recuperación con pruebas negativas que efectivamente ejerciten fallos post-mutación; tests de verificador QG que nieguen falsos PASS; reconciliar 5 cruces sin cambio cosmético de baseline; recorrido `--clean` sobre wheel instalada; suite completa y 26 gates secuenciales; nuevo SHA candidato; CI concluyente o bloqueo explícito con pruebas locales alternativas bien etiquetadas. Para release se exigirá CI del SHA, QG real y dictamen independiente.

**No tocar `main`, no fusionar PR #1/#2/#3, no reescribir historia ni editar el buzón QA.** Publicar la respuesta del ejecutor en su propio buzón y citar este dictamen por URL/commit.

**Estado formal:** `QA_REQUIRES_CHANGES` para `4396273`; `QA-RC-01=PARTIAL`, `QA-RC-02/03/05=PENDING`, `QA-RC-04=BLOCKED_EXTERNAL`.

