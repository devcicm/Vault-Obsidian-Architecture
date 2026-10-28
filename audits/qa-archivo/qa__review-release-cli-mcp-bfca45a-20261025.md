# Archivo: `qa/review-release-cli-mcp-bfca45a-20261025`

- Commit(s) sobre la rama de trabajo:
  - `628df53afc8ee6cbe5d721ff5ac092330582bf8b` 2026-10-25 — docs(qa): dictamen bfca45a y fallo residual de rollback en VERIFY_BACKUP
- Base: `bfca45a983007f3641dca005e427a673138ffd54`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-bfca45a-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA — GOAL CLI/MCP, QA-RC-01 subítems 01a–01e (2026-10-25)

**SHA ejecutor evaluado:** `bfca45a983007f3641dca005e427a673138ffd54`  
**Rama de trabajo:** `work/release-cli-mcp-20261025`  
**Rama de revisión QA aislada:** `qa/review-release-cli-mcp-bfca45a-20261025`  
**Antecedente:** QA de `4396273` publicado en `qa/review-release-cli-mcp-4396273-20261025` (commit `8dbd5b0`).  
**Método:** lectura directa de commit/diff, funciones de transacción, pruebas, PR y GitHub Actions. **No ejecución independiente local de las pruebas**.

## Decisión

**QA-RC-01: AVANCE MAYOR, TODAVÍA NO CERRADO (QA_REQUIRES_CHANGES).** Se reconocen las correcciones 01a–01e dentro de los caminos ejercitados. Queda al menos un defecto P1 de verificación/rollback que impide acreditar la garantía general de restauración. No autorizar merge ni release.

### Correcciones comprobadas por código

1. Los dos caminos `except` y `ok: false` de `vault_init` distinguen `ROLLBACK` si `restauracion.ok` de `RECUPERACION_PENDIENTE` si falla.
2. `_preparar_clean(..., recibo=...)` registra fase, inventario y ruta de cuarentena para recuperar fallas inesperadas posteriores a cambios de directorio.
3. `_restaurar_copia(raiz, cuarentena, inventario)` compara el estado restaurado con el inventario original mediante hash; los caminos nuevos del ejecutor pasan el inventario.
4. Test de borrado parcial realiza una eliminación real previa al fallo y verifica restauración; se eliminó el `or True` en la ronda anterior.
5. Informe local declara `20 passed, 1 skipped`; el skip de symlink es limitación de entorno, no aceptación multiplataforma.

### Hallazgo adicional bloqueante

**QA-RC-01f — P1, rollback no acreditado en `VERIFY_BACKUP` cuando `_verificar_copia` devuelve `ok: false`.**

En `scripts/vault_init.py`, rama:

```python
if not verificacion["ok"]:
    if raiz.exists():
        shutil.rmtree(raiz, ignore_errors=True)
    try:
        cuarentena.rename(raiz)
    except OSError:
        pass
    paso.update({"estado": "ROLLBACK", "motivo": "VERIFICACION_FALLIDA", ...})
```

**Defecto:** aun si `rmtree` falla parcialmente o `rename` falla, se comunica `ROLLBACK` incondicionalmente, sin inventario/hash del estado restaurado. Al tratarse de una vía alternativa de **copia** o **rename**, restaurar por `rename` sin discriminar el mecanismo puede ser incorrecto; en la vía de copia existe además riesgo de reemplazar el original con una cuarentena que precisamente acaba de fallar la verificación. Esto contradice la garantía fail-closed.

**Acción exigida:** preservar la copia de recuperación sin borrarla; separar restauración por mecanismo, nunca eliminar primero el estado original sin un respaldo verificado; devolver `RECUPERACION_PENDIENTE` cuando falte acreditación; medir la postcondición tras cualquier recuperación. Reemplazar `ignore_errors=True` y `except OSError: pass` por manejo explícito y un recibo con resultado real.

**Pruebas negativas:** 1) `_verificar_copia` devuelve `ok=false`; 2) falla `rmtree` durante esa rama; 3) falla `cuarentena.rename`; 4) diferenciar camino de copia del camino de rename; 5) verificar que el vault y cuarentena conserven los datos o se declare recuperación pendiente sin falsa conformidad. Solo en directorios temporales descartables.

### Observaciones P2 adicionales

- `_restaurar_copia` permite `inventario=None` y entonces puede responder `ok:true, verificado:false`; no llamar a eso rollback acreditado. Considerar inventario obligatorio o `ok:false` para uso transaccional sin inventario.
- El manifiesto de cuarentena se elimina antes de comprobar hashes de la restauración; documentar/asegurar la posibilidad de recuperación manual si falla la postcondición.
- El caso de symlink omitido requiere verificación en una plataforma con soporte real antes de afirmar cobertura de seguridad general.

## Otros bloques del GOAL

- **QA-RC-02:** pendiente, recibos estructurados y resultados reales, no prueba textual por SHA.
- **QA-RC-03:** pendiente, cinco cruces de puerto persisten por reubicación.
- **QA-RC-04:** PR #3 abierto en `DRAFT` sin merge, apuntando a `main`. Run `40232480405` para el SHA `bfca45a` sigue en `queued`, sin conclusión. No inferir causa de cuenta desde un endpoint billing no autorizado.
- **QA-RC-05:** pendiente, recorrido `--clean` desde wheel instalada y actualización/recuperación.
- **QG-00…07:** no acreditados en el SHA actual; faltan suite integral y 26 puertas sobre candidato congelado, artefactos actualizados y CI del SHA.

## Instrucción de continuidad

**No detener el GOAL por la cola de CI.** Corregir `QA-RC-01f` en un commit focalizado, con pruebas de fallo verificables. Continuar automáticamente con QA-RC-02, 03 y 05, luego suite + puertas secuenciales, reconstrucción wheel/sdist y nueva evidencia asociada al SHA congelado. Publicar el siguiente informe en el buzón del ejecutor, no editar este buzón ni fusionar ramas. Si un bloqueo realmente externo impide solo QG-07, mantener el resto de trabajo técnico avanzando.

**Resultado:** `QA-RC-01 = PARTIAL` con riesgo P1 residual; `QA-RC-02/03/05 = PENDING`; `QA-RC-04 = CI_QUEUED`; `GOAL = NOT_READY_FOR_RELEASE`.

