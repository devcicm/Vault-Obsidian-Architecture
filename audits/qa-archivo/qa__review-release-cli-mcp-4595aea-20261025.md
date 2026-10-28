# Archivo: `qa/review-release-cli-mcp-4595aea-20261025`

- Commit(s) sobre la rama de trabajo:
  - `f7100898d9dd6a1bd0c00abacef86b72a9b06138` 2026-10-25 — docs(qa): dictamen intermedio 4595aea sobre rollback y evidencias QG
- Base: `4595aea4c8284b523966cfb3ddde0c87cd7092aa`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-4595aea-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



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

