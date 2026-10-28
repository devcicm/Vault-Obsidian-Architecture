# Archivo: `qa/review-release-cli-mcp-408eb23-20261026`

- Commit(s) sobre la rama de trabajo:
  - `e30e6686a560b80f2ee18926203d8a9d10b3ae17` 2026-10-26 — docs(qa): revisar R12 408eb23, fallos macOS y nueva regresión Windows
- Base: `408eb2344f089daf6fe6bf9a73f24b6b4b288520`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-408eb23-20261026`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R12, candidato 408eb23 (2026-10-26)

**SHA exacto del producto examinado:** `408eb2344f089daf6fe6bf9a73f24b6b4b288520`  
**Rama implementación:** `work/release-cli-mcp-20261025`.  
**Rama QA aislada:** `qa/review-release-cli-mcp-408eb23-20261026`.  
**Reporte del ejecutor:** `audits/handoff/RESPUESTA-DEL-EJECUTOR.md`.  
**Documentos de decisión:** `audits/fase2/INFORME-READINESS-TERCEROS.md`, `audits/fase2/POLITICA-CERTIFICACION-PRODUCTO.md`, `audits/architecture/PLAN-B-MIGRACION-CRUZES.md`.

**Método:** inspección real de GitHub (SHA, diff, políticas, tests, CI jobs y logs concluidos en Windows y macOS). **No se ejecutaron localmente** pytest, wheel, 26 puertas, E2E ni el colector; sus cifras locales se atribuyen al informe del ejecutor y no a una certificación de QA. No se modifica ningún código en la rama del ejecutor ni `main`.

## Veredicto

**QA_REQUIRES_CHANGES / RELEASE_NOT_APPROVED.** Las reparaciones R12 de CI Windows/Linux son mejoras verificables y la mayoría de esos jobs pasó. **No se acepta la conclusión de que los pendientes técnicos terminaron o que macOS sigue NOT_RUN por falta de runners.** La matriz macOS sí ejecutó y reveló fallos nuevos. `QG-07` no puede acreditar PASS mientras el run del SHA objetivo tenga `conclusion=failure`.

### Evidencia independiente de la CI (revisada cuando los runs ya habían terminado)

| Run | SHA | Éxitos | Fallos | Estado |
|---|---|---:|---:|---|
| `40340865847` | `408eb23` | 21/25 | **4/25** | `completed/failure`; los 4 fallos son `Validate Vault Spec (macos-latest, 3.9, 3.10, 3.11, 3.12)` |
| `40348953734` | `6660abf` (documental) | 21/25 | **4/25** | `completed/failure`; mismos 4 validate de macOS |
| `40349132455` | `dfc6a06` (documental) | 20/25 | **5/25** | `completed/failure`; macOS 4 y Windows 3.10 1 |

**Nota de identidad:** `408eb23→6660abf→dfc6a06` solo cambia `INFORME-READINESS-TERCEROS.md`, `RESPUESTA-DEL-EJECUTOR.md` y `PROTOCOLO-QA.md`. Producto sin delta, **pero los jobs posteriores no sustituyen la obligación de verificar su propio SHA**. En la última inspección el HEAD de trabajo era `dfc6a06`; `main=1c34754258441550139ce895e182ab219c93f9bb` y PR #3 OPEN/DRAFT, sin merge.

### QA-R12-01 — P1: fallas macOS reales (no problema de runner en cola)

Los logs del run `40340865847` indican:

1. **Servicio HTTP/token**: `tests/test_token_service_seguridad.py` falla en `Servicio.__init__` con `RuntimeError: el servicio no abrió el puerto`; provoca 1 FAIL y **11 ERROR** por fixture de servidor en macOS 3.9 y también en 3.10/3.11/3.12. El test inicia un proceso con stderr a PIPE pero, al agotar su plazo de arranque, arroja error **sin adjuntar stderr, returncode, comando, socket o PID**. La causa raíz **NO está demostrada**. Instrumentar arranque/puerto, capturar stderr de forma acotada y diagnosticar si servidor falla, enlaza a otra interfaz, es inaccesible, o si el test de 30s necesita una condición de readiness distinta; no tapar con sleeps ni skip ni relajar autenticación/anti-DNS-rebinding.
2. **Migración frontmatter**: `tests/test_onboard_legacy_frontmatter.py::test_heal_legacy_paso_curar_todas_las_notas_legacy` espera `escaneadas=3` pero recibe **5** en las cuatro versiones de macOS. Identificar exactamente qué archivos adicionales se enumeraron, su ruta y naturaleza (p. ej. auxiliares de filesystem o escaneo fuera del root), aislar raíz de prueba y corregir filtro/contabilidad según contrato; nunca editar el esperado a 5 sin prueba semántica de que las cinco notas son legítimas.
3. **File lock**: en macOS 3.11 además falló `tests/test_file_lock_entre_procesos.py::test_file_lock_no_deja_entrar_a_dos_procesos` con al menos un hijo que emitió traceback de locking. Obtener stderr íntegro y probar exclusión mutua en filesystem APFS; no afirmar flake ni corregir a ciegas.

Todos los `Product gates (wheel)` de macOS fueron `completed/success`: esa evidencia es positiva **para ese subconjunto**, no para los 25 jobs.

### QA-R12-02 — P1: regresión posterior en Windows 3.10

En run `40349132455` (SHA `dfc6a06`), `Validate Vault Spec (windows-latest, 3.10)` falló en `tests/test_backup_base64.py::test_ap36_el_restore_no_lee_un_backup_fuera_del_vault` con `shutil.Error` por archivo de `.locks` desaparecido durante `copytree`. Investigar concurrencia entre locks y copia de runtime/fixture; identificar escritores y establecer snapshot estable/exclusión coherente, sin eliminar el test de contención. Es un **fallo observado en un run posterior**, no una conclusión sobre el resultado de Windows en el run congelado `408eb23`, donde Windows fue success.

### QA-R12-03 — P1: clasificación errónea de CI en política e informe

`audits/fase2/politica_qg.py` conserva la condición `_ci_concluyente() == (conclusion=="success")`, correcta para impedir PASS, pero etiqueta todo `failure` como `CI_PENDIENTE` cuando en realidad CI **concluyó negativamente**. Separar **`CI_FAILED`** (run completed/failure, jobs rojos y causa vinculada) de **`CI_PENDING`** (queued/in_progress), preservando la regla de no liberar. No reemplazar bloqueos por PASS ni cambiar sin autorización la política de waiver. Actualizar readiness y protocolo: macOS actualmente `EXECUTED/FAILED`, no `NOT_RUN`. Tests negativos para `success`, `failure`, `queued`, jobs parciales, SHA ajeno.

### QA-R12-04 — Arquitectura/QG pendientes, no por ello "no técnicos"

- **QG-00/01**: 10 divergencias Archify siguen abiertas, 5 cruces de código, sin decisión del propietario. El `PLAN-B-MIGRACION-CRUZES.md` es una **propuesta**, no una eliminación aceptada. Riesgo específico: sustituir imports de símbolos por ejecución de comandos externos puede ocultar la dependencia en el grafo estático sin eliminar el acoplamiento operativo; el propio plan reconoce compatibilidad y subprocess cost. Antes de ratificar B, exigir criterio de *independencia semántica real*, tests de dependencia, empaquetado y side-effects, y retorno observable. No retocar snapshot/baseline para forzar QG.
- **QG-02**: `POLITICA-CERTIFICACION-PRODUCTO.md` propone evaluar tanto runtime limpio como sandbox; preserva AP-36 y no autoriza borrar `vault-backups` externos. La contaminación externa se inventaría y decide por su dueño; un runtime limpio PASS no debe borrar una violación medida en el sandbox. Política **no ratificada**.
- **QG-03..06**: recibos PASS reportados por ejecutor, pero su acreditación queda subordinada a QG-00 y al SHA/CI verificados. QA no los ha reproducido localmente.
- **QG-07**: **NO PASS por CI real failed**, además de prerrequisitos QG-00/01/02. No hay autorización de release. Constitución DRAFT y decisión de propiedad siguen pendientes.

### Secuencia recomendada al ejecutor

1. Leer logs completos de macOS y Windows citados. Para macOS: diagnosticar servicio/token, escaneo legacy 5≠3 y exclusión `file_lock`. Para Windows: snapshot coherente de `.locks`. Crear regresiones que fallen antes y pasen después, y observabilidad robusta.
2. Corregir problemas de producto/harness sin desactivar tests, no usar sleeps ni waivers ni cambiar aserciones para maquillar. Validar focalizado y en Linux/Windows/macos; CI debe acreditar **25/25** jobs con conclusión success en nuevo SHA.
3. Cambiar `politica_qg` solo para **distinguir CI fallida de pendiente**, sin permitir PASS ni ampliar el catálogo por atajo. Reconciliar `INFORME-READINESS-TERCEROS.md`, `CI-diagnostico.md`, `PROTOCOLO-QA.md` y buzón del ejecutor con el estado real.
4. Producir un manifiesto único nuevo SHA para código+wheel/sdist+suite+E2E+26 puertas+recibos QG, repetir validaciones afectadas, congelar y solicitar QA independiente. Nada de reuse de ejecuciones con SHA anterior como aprobaciones.
5. Mantener decisiones del propietario separadas: ratificación de Constitución, decisión A/B/C sobre divergencias, alcance QG-02, backups ajenos, historia publicada, lanzamiento. QA no ratifica ni autoriza por cuenta del propietario.

**Veredicto final de R12: `QA_REQUIRES_CHANGES`, `MACOS=EXECUTED_FAILED`, `CI_408eb23=COMPLETED_FAILURE`, `QG07=NOT_APPROVED`, `MAIN_UNCHANGED`. Mantener PR #3 en DRAFT, sin merge, sin release.**

