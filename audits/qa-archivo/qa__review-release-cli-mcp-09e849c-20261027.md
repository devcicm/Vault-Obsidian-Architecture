# Archivo: `qa/review-release-cli-mcp-09e849c-20261027`

- Commit(s) sobre la rama de trabajo:
  - `7d2679ab739fb7da28eedfab30b320ce6ae36020` 2026-10-27 — docs(qa): dictamen R16 UTF-8 y política compuesta fail-closed
- Base: `09e849cde3aa1bcb4d5d79743fad5ac2ce9a1c17`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-09e849c-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R16, candidato 015b776, fix 55ad340 y HEAD documental 09e849c (2026-10-27)

**Product SHA congelado:** `015b7765b80cac21c6dcf859ae075d036cd01def`; tree `d190fd243567556e824795154b6fd44bd76309d5`.  
**Commit de corrección R16:** `55ad340918caca237ad18bcc4aec64b05a9333d0`.  
**HEAD documental evaluado:** `09e849cde3aa1bcb4d5d79743fad5ac2ce9a1c17`.  
**Rama ejecutora:** `work/release-cli-mcp-20261025`.  
**Rama aislada QA:** `qa/review-release-cli-mcp-09e849c-20261027`.  
**Dictamen antecedente:** `e47d62f0135cd054be2267b77a72fc26007fc97d` (R14).

**Método:** revisión estática de diffs, pruebas y documentos, inspección GitHub de corridas y 25 jobs de Actions, comparación product SHA vs commits posteriores, propuesta DEC-02/DEC-03/DEC-04 y política compuesta. **QA no ejecutó localmente pytest, E2E o wheel; los resultados 6334/13/0 y 27/27 son del ejecutor, no pruebas independientes.**

## Veredicto R16

**R16: CORRECCIÓN FOCALIZADA ACEPTADA; CI DEL FIX 25/25 VERIFICADA. RELEASE SIGUE BLOQUEADO.**

- Run `40451686234` SHA `e0fc775`: failure documentado, 12 jobs `Validate` fallidos por el guard de decodificación locale; 13 jobs de producto PASS según evidencia CI del agente. R16 agrega `encoding="utf-8"` en subprocess en `tests/test_manifiesto_candidato.py`, sin rebajar el guard.
- Run `40456389815` SHA `55ad340`: comprobado directamente `completed/success`, **25 jobs distintos, todos completed/success** (12 validate + 12 product gates + lint). Corroboración del cierre focalizado de portabilidad.
- Run `40442954197` SHA de producto `015b776`: completado 25/25 según revisión R14 previa; **no confundir esta CI del producto con autorización de QG-07 ni con QA/owner approval**.
- Compare `015b776 → 55ad340`: no cambia `scripts/`, `vault/`, `mcp/` ni `pyproject.toml`; se modifica documentación/tests y propuestas ejecutables bajo audits. La identidad de la wheel permanece declarada para 015b776; validar su hash real al publicarse.
- Compare `55ad340 → 09e849c`: solo cambia `audits/fase2/CANDIDATO-RELEASE.yaml`, `INFORME-READINESS-TERCEROS.md` y el buzón del ejecutor; no modifica producto ni tests.
- Run `40464661392` del HEAD documental `09e849c` estaba **in_progress** (13 jobs completed/success; 12 aún in_progress) durante la consulta: **NO afirmar 25/25 ni éxito del HEAD final hasta conclusión**.
- PR #3 OPEN/DRAFT, sin merge; `main=1c34754258441550139ce895e182ab219c93f9bb` intacto.

## Hallazgo nuevo — QA-R16-QG02-01 (P1 para aprobar la propuesta DEC-03=C)

**La propuesta de política compuesta para QG-02 NO es todavía fail-closed respecto a la autorización del propietario.** En `audits/fase2/politica_certificacion_compuesta.py`, `registrados_por_id = {str(r.get("id")):r ...}` y el flujo `if registro is not None` añaden un residuo registrado sin validar que `decision_ref` exista, no sea vacío, corresponda a un documento real y contenga ratificación expresa del propietario. Así, con controles ejecutados y SHA iguales, el motor puede regresar `PASS` con `residuos_registrados=[{"id":"INC-0001","decision_ref":null}]`. Peor: el test positivo `test_positivo_todo_limpio_es_pass_y_un_residuo_con_decision_queda_listado` pasa una cadena que literalmente dice **"DEC-04 (pendiente de firma ... sin firma real seria BLOCKED)"** y espera PASS. Eso contradice el anexo de propuesta del propietario `cc05eab`, que exige `DEC-04=PENDING`, y el contrato declarado `RESIDUO_SIN_DECISION ⇒ BLOCKED`.

**Acción:** corregir SOLO el ejecutable propuesto y sus tests negativos (no aplicar a catálogo/política QG de producción sin DEC-03 firmada). Exigir prueba de decisión formal, identificador y alcance (residuo/norma/ruta/huella), estado ratificado, firmante, fecha, referencia inmutable y custodias aplicables; fallo de validación ⇒ BLOCKED (no PASS). Un mero texto `decision_ref`, especialmente "pending", es insuficiente; no depender de texto libre. Los registros falsos, incompletos, vacíos, no ratificados, ajenos y con identidades de residuo ambiguas deben quedar rechazados. Negativas con `decision_ref:null`, ausente, "pendiente", referencia no verificable y registro del mismo ID para otra ruta. Con DEC-04 todavía pendiente, **QG-02 debe seguir BLOCKED** aun con la propuesta C.

**QA-R16-QG02-02 (P2, integridad de la evidencia de runtime):** la propuesta toma `(total_violations or 0) > 0` para el runtime. Un `total_violations=0` con `violations` no vacía o `total_violations` ausente no desencadena FAIL. Exigir esquema coherente: entero no negativo, array de hallazgos, conteo consistente; contradicción/ausencia ⇒ BLOCKED o FAIL según el tipo de inconsistencia, jamás PASS. Agregar negativos de auditoría incompleta/contradictoria. Ninguna de estas correcciones supone ratificar DEC-03.

## Decisiones pendientes (NO inferir ni automatizar)

- **DEC-02:** el anexo del propietario `cc05eab` registra preferencia **B CONDICIONADA**, no ratificación. Elegir expresamente I2-a/b/c y COST-a/b/c, umbral de latencia, ventana de deprecación y parámetros de migración. I2-c no elimina el cruce real; COST-c deja deuda parcialmente abierta. B requiere código, tests I1–I5, nuevo candidato, E2E, matriz CI y nuevo QA.
- **DEC-03:** preferencia **C CONDICIONADA**, no aplicada. Además del hallazgo de procedencia/ratificación antes indicado, el contrato final requiere aprobación formal. No editar `catalogo-qg.yaml` o `politica_qg.py` ni aceptar AP-36 sin firma.
- **DEC-04:** `vault-backups` externo, **66 archivos y ~854 KiB según medición del ejecutor**. Mantener intacto. El runbook está en fases 1–3 de lectura/verificación; **no ejecutar archivo, traslado, compresión ni purga sin autorización específica escrita del dueño de datos**.
- **DEC-01:** Constitución DRAFT; ratificación o enmienda del propietario.
- **DEC-05:** retención de la historia pública o reescritura, reservada al propietario. Sin force-push ni cambio de SHA sin aprobación.
- **DEC-06:** autorización de distribución **posterior a QA favorable y QG efectivos**. Propuesta de alcance: CLI producto + MCP stdio, sin soporte certificado de SSE/HTTP ni `python -m cli` no empaquetada.

## QA-R16-DOC-01 (P2): comentario HEAD padre y prueba tienen contratos distintos

`CANDIDATO-RELEASE.yaml` aún afirma que **HEAD^ == product_sha**, pero en `tests/test_manifiesto_candidato.py` la condición real permite fallback `git merge-base --is-ancestor product_sha HEAD`; con R16 hay varios commits documentales posteriores. El test positivo demuestra ascendencia, no paternidad inmediata. Cambiar la descripción canónica a "product_sha es ancestro del HEAD documental", indicar `doc_parent_sha` de publicación inicial cuando aplique y reforzar negativos para SHA producto ajeno; **no modificar el product_sha para maquillar esta diferencia**.

## Estado de la matriz de release

**Acreditado independientemente en esta ronda:** corrección UTF-8 en código, CI 25/25 de `55ad340`, CI previa del product_sha según QA R14, distinción HEAD documental/producto y estado de PR/`main`.

**No acreditado como liberable:** QG-00/QG-01 (Archify / decisión DEC-02), QG-02 (AP-36 / DEC-03+DEC-04), QG-07 (prerrequisitos QG), dictamen final de la nueva arquitectura, autorización DEC-06, tag y publicación. Recibos locales QG-03..06 son evidencia de ejecución local publicada como manifiesto, no firma QA independiente de sus bytes originales.

**Acción técnica autorizada para el ejecutor sin ratificación:** corregir la *propuesta no aplicada* de DEC-03 y sus tests, reconciliar comentarios del manifiesto, actualizar solo informes derivados; realizar benchmarks/lecturas en sandboxes. Dejar intactos QG de producción, deuda ratificada, baselines, producto y datos reales hasta autorización.

**Estado formal:** `QA_R16_REGRESSION=ACCEPTED_SCOPED`, `CI_FIX_SHA=25/25_SUCCESS`, `DEC_02=OWNER_PENDING`, `DEC_03=OWNER_PENDING_AND_PROPOSAL_REQUIRES_CHANGE`, `DEC_04=OWNER_PENDING`, `RELEASE_BLOCKED`, `NO_MERGE`, `NO_RELEASE`.

