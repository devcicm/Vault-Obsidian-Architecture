# Archivo: `qa/review-release-cli-mcp-29c1a15-20261025`

- Commit(s) sobre la rama de trabajo:
  - `a9e0143b5e246e2766fece5273bd7bfa20632707` 2026-10-25 — docs(qa): dictamen 29c1a15 y falsos PASS/CLI QG en R08
- Base: `29c1a15cfcb212dedbcf1b6794c238fd815a4aa5`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-29c1a15-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R08, commit 29c1a15 (2026-10-25)

**Commit ejecutor:** `29c1a15cfcb212dedbcf1b6794c238fd815a4aa5`  
**Rama ejecutora:** `work/release-cli-mcp-20261025`  
**Rama QA independiente:** `qa/review-release-cli-mcp-29c1a15-20261025`  
**Dictamen base:** `fabe442765ca5bdf5c9ab68201058a34e716b2e3` (R07, SHA 5836474).  
**Método:** lectura GitHub del SHA, diff, colector/CLI/tests, harness R07, contrato QG, PR y Actions. **No ejecuté localmente suite/puertas/wheel; sus resultados son reportes del ejecutor hasta que se adjunte evidencia reproducible.**

## Veredicto

**QA_REQUIRES_CHANGES — GOAL IN_PROGRESS, no READY_FOR_QA final.** Se confirman avances en QA-RC-02d/e/f y que `main` remoto permanece intacto, pero subsisten defectos bloqueantes de acreditación y de operabilidad del propio colector. El bloqueo CI es independiente de esas tareas técnicas pendientes.

### Mejoras verificadas

1. `estado_ci()` ahora intenta consultar jobs por API para el run exitoso del SHA y verifica nombres exactos de jobs requeridos, `status=completed` y `conclusion=success`; sin acceso devuelve no verificable.
2. `SUBCHECKS_OBLIGATORIOS` rechaza recibos que omitan subcontroles declarados.
3. `ejecutar_verificador()` invoca un comando configurado y registra exit, salida, hash y recibo fuera del árbol si `salida` apunta afuera.
4. Se ampliaron casos unitarios. El ejecutor informa árbol limpio, rama `29c1a15`, sin merge, y admite honestamente que faltan suite/26 puertas/harness finales.

### Nuevos hallazgos que impiden aceptar cierre de QA-RC-02

**QA-RC-02g — P1: PASS masivo de subchecks no ejecutados.**
`audits/fase2/colector_qg.py`, `ejecutar_verificador()`: después de ejecutar **un** comando, calcula `declarado = PASS` solo con exit 0 (y una búsqueda textual de `"ok": false`) y asigna `checks = {sc: declarado for sc in SUBCHECKS_OBLIGATORIOS[gate]}`. Esto **autocertifica** todos los subchecks sin ejecutarlos individualmente. Ejemplo: QG-04 registra `saneamiento=PASS` y `pip_audit=PASS` cuando solamente corre `comprobar_saneamiento.py`; QG-06 registra `instalacion_limpia=PASS` al ejecutar exclusivamente `python -m build`; QG-00 registra todos los estados con `python tests/test_vault_init_clean.py`. En ese archivo de tests no hay `pytest.main` ni `if __name__ == '__main__'`, por lo que lanzarlo como script Python no ejecuta tests; su exit 0 es insuficiente incluso para ese control. La prueba positiva del ejecutor usa stub que imprime `{"ok": true}` y espera todos los subchecks PASS, confirmando el defecto.

**Cierre:** modelar **cada** subcheck con su verdadero verificador/comando, artifact schema/criterio y recibo individual; agregador determina QG PASS solo si TODOS están acreditados y el catálogo coincide. Sin comprobación, `NOT_RUN`. Pruebas negativas por subcheck faltante y comandos sin tests; ningún status se derive masivamente de exit de un único comando.

**QA-RC-02h — P1: CLI del colector rota por firma incompatible.**
La función `colectar(... consultar_jobs=...)` ya NO recibe `jobs_ci`, pero `main()` aún invoca `colectar(... jobs_ci=jobs)` después de parsear `--jobs-ci`; esa ruta falla con `TypeError: unexpected keyword argument 'jobs_ci'`. Falta además un camino CLI integrado para **ejecutar** verificadores y generar recibos; el productor existe solo como función llamada por tests, no como pipeline invocable y completo.

**Cierre:** corregir CLI/API, añadir pruebas reales de proceso `python audits/fase2/colector_qg.py --help` y el flujo invocado con SHA, salir con código y JSON esperado, integrar `--ejecutar-verificadores` o comando coherente que produzca recibos fuera del árbol, sin autocertificar ni simular.

**QA-RC-02i — P1: CI permite jobs sin vínculo acreditado al run y duplicados.**
`estado_ci()` considera pertenecientes al run los jobs cuyo `run_id` es `None`, y el caso positivo de tests devuelve jobs **sin** `run_id`. Acepta varias entradas con el mismo nombre requerido cuando todas declaran success; no valida unicidad de job por matriz. `sobrantes` permite nombres extras que empiecen con nombre requerido. Por otro lado, la consulta de `gh api .../jobs` usa la primera página sin comprobar paginación/total_count.

**Cierre:** si la API no suministra `run_id` en cada job, acreditar la asociación mediante la respuesta auténtica al endpoint del run seleccionado y metadatos de esa petición, nunca mediante listas arbitrarias. Validar `total_count`/paginación y cobertura exacta, duplicados y estados de todos los jobs obligatorios. Tests con run_id ausente en datos aportados manualmente, duplicados de job requerido, nombres extra ambiguos, más de una página.

### Hallazgos anteriores abiertos

**QA-RC-05 — P2/contrato funcional:** `recorrido_terceros_r07.py` sigue sin modificación en `29c1a15`; no se ha demostrado 19/19. Mantiene carpetas fijas bajo TEMP con borrado directo, hash de entrada en lugar de archivo persistido, `cuarentenas == 1`, mezcla restore mediante `copytree(dirs_exist_ok=True)` y protocolo MCP en batch sin `notifications/initialized`. Riesgo especial: el harness puede borrar carpetas preexistentes. Cambiar a sandbox propio por run y protección de ruta antes de continuar. Registrar inventario SHA256 y cliente secuencial.

**QA-RC-03 — pendiente:** los cinco cruces off-port permanecen. No hubo ratificación expresa del propietario para convertirlos en deuda permanente. No ampliar ni cambiar baseline por declaración; presentar elección A/B/C o eliminar genuinamente.

**QG:** 00..06 sin recibos contemporáneos auténticos y sin ejecución integral concluida del SHA; 07 BLOCKED por CI. Aunque un esquema de recibo sea válido, sin ejecución de TODOS los controles no equivale a PASS.

**CI/PR:** rama del ejecutor = `29c1a15`; PR #3 OPEN/DRAFT con base `main`, sin merge; `main = 1c34754258441550139ce895e182ab219c93f9bb`. Run `40244460688` para `29c1a15`: `queued` sin conclusión, no atribuir causa concreta a billing sin verificación administrativa.

## Instrucción de salida R09

No repetir auditoría general ni reiniciar GOAL. Hacer en la siguiente ejecución: (1) corregir QA-RC-02g/h/i y demostrar negativos + CLI E2E real; (2) corregir harness QA-RC-05 y ejecutarlo sobre wheel con sandbox seguro, protocolo MCP y 19/19; (3) ejecutar suite y 26 puertas del SHA actualizado, preferiblemente en serie; (4) **publicar código primero y congelar SHA**, luego producir y validar recibos externos por subcheck, sin modificar el candidato; (5) mantener QG-07 BLOCKED hasta CI concluida y requerir decisión de arquitectura separada.

**Dictamen:** `QA_REQUIRES_CHANGES`. No merge a main, no release, no force-push, no reescritura de historia ni pruebas destructivas sobre datos no descartables. El agente puede continuar automáticamente en el alcance técnico ya autorizado.

