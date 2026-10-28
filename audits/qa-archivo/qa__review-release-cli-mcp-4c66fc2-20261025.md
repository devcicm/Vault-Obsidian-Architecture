# Archivo: `qa/review-release-cli-mcp-4c66fc2-20261025`

- Commit(s) sobre la rama de trabajo:
  - `1e75d94d007dfe5eeee03e999348d3410c11e18b` 2026-10-25 — docs(qa): dictamen R07 4c66fc2 y brechas CI/QG y recorrido de terceros
- Base: `4c66fc2971933d1e8c3a7a60b17d9145b9e0db5c`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-4c66fc2-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R07, candidato intermedio 4c66fc2 (2026-10-25)

**Repositorio:** `devcicm/Vault-Obsidian-Architecture`  
**SHA del ejecutor:** `4c66fc2971933d1e8c3a7a60b17d9145b9e0db5c`  
**Rama ejecutora:** `work/release-cli-mcp-20261025`  
**Rama aislada de QA:** `qa/review-release-cli-mcp-4c66fc2-20261025`  
**Revisión previa QA-RC-02:** `f7100898d9dd6a1bd0c00abacef86b72a9b06138` en rama `qa/review-release-cli-mcp-4595aea-20261025`.
**Método:** lectura independiente de commits/diff, código del colector y tests, catálogo QG, repositorio de evidencias, PR y jobs de GitHub Actions. **QA no ejecutó localmente la suite ni el recorrido E2E.**

## Decisión

**R07 IMPLEMENTACIÓN PARCIAL VERIFICADA; NO APROBADO COMO RELEASE CANDIDATE FINAL.** El estado honesto es `IN_PROGRESS / NOT_READY_FOR_FINAL_QA`, no `QG_PASS` ni `RELEASED`.

- **QA-RC-01f:** aceptado previamente en alcance; no se cambió `vault_init.py` en el nuevo commit y no hay nueva evidencia de regresión.
- **QA-RC-02a:** se añadió requisito de artefacto, whitelist de verificador+comando y detección básica de `{"ok": false}`. Mejora auténtica, **NO equivale todavía a ejecutar/interpretar los verificadores obligatorios**.
- **QA-RC-02b:** se añadió matriz nominal (25 jobs) y workflowName obligatorio; **sigue una vía de PASS falsa por ausencia de jobs**.
- **QA-RC-02c:** JUnit enlazado por SHA-256 a recibo; `git` y auditoría comprueban exit codes. Aceptado como corrección focalizada; no implica procedencia confiable frente a falsificación de recibo local.
- **QA-RC-03:** cinco `off_port_crossings` siguen declarados: `vault_norms` a `vault_mcp_catalog`, `vault_smoke` (x3) y `vault_voice`. No hay ratificación del propietario para excepción permanente: **NO CERRADO**.
- **QA-RC-05:** el agente reporta 15–16/19 desde nueva wheel y tres defectos del harness. QA no puede verificar esa cifra ni el recorrido exacto desde GitHub: el archivo citado `audits/fase2/recorrido_terceros_r07.py` **NO EXISTE en el árbol del SHA examinado**. El script previo `audits/fase2/recorrido_mvp.py` sí existe, pero no sustituye el nuevo recorrido de `--clean`.
- **Suite/puertas:** 6250 pass/13 skip y 26/26 atribuidos por el ejecutor a una revisión anterior al SHA final. Las reejecuciones sobre `4c66fc2` figuran en curso, **no concluidas ni verificadas**.
- **CI:** run `40237812081` del SHA actual contiene **25 jobs, todos `queued` y ninguno concluido** al revisar. `QG-07=BLOCKED`. La causa específica (billing, permisos, cuota) **no está probada**.
- **Git:** PR #3 OPEN/DRAFT no fusionado, `main=1c34754258441550139ce895e182ab219c93f9bb` intacto.

## Hallazgos que impiden acreditar QA-RC-02 como completo

**QA-RC-02d — P1, CI matriz opcional y conclusiones desconocidas aceptadas.** En `audits/fase2/colector_qg.py`, `estado_ci(..., jobs=None)` **omite toda la validación de jobs** y aún puede retornar `success` si el run informa `completed/success`. La CLI solo lee jobs cuando se le suministra opcionalmente `--jobs-ci`, por lo que el camino normal no los consulta. Cuando sí hay jobs, `j.get("conclusion") not in (None, "success")` **permite `conclusion=None`**, y el matcher `startswith()` sobre nombres no prueba identidad exacta ni asociación al run exitoso. Se acepta un conjunto de jobs no ligado explícitamente al run ID elegido. **Reparación:** obtener siempre los jobs del run correcto mediante API/CLI (o marcar BLOCKED ante falta de permisos), cotejar workflow y matriz esperada, exigir cada job `status=completed`, `conclusion=success`, run ID coincidente, sin duplicados ni entradas desconocidas que afecten requisitos. No dar PASS con `jobs=None` ni con `conclusion=None`. Contrastar requisitos con definición efectiva del workflow. Negativas: success sin jobs, job queued/null, jobs de otro run, nombre que solo comparte prefijo, duplicados.

**QA-RC-02e — P1, verificador autorizado NO equivale a criterio QG completo.** El diccionario `GATE_VERIFICADORES` reduce QG-00 a `tests/test_vault_init_clean.py` aunque el catálogo exige además saneamiento, Archify, identidad y trazabilidad; QG-04 a `comprobar_saneamiento.py` aunque incluye dependencias, rutas y protección `--clean`; QG-05 a paridad sin el chequeo AP-40; QG-06 a `python -m build --wheel --sdist` sin instalación limpia ni gate del contenido. QG-03 se infiere de JUnit pero el catálogo requiere también e2e de recuperación y gates del producto. `leer_recibo` acepta un artefacto JSON con solo `{"ok":true}`, siempre que el recibo autodeclare el comando autorizado y PASS, sin ejecución del comando ni interpretación del contrato de la puerta. Las pruebas positivas construyen precisamente este tipo de fixtures. **Reparación:** definir checklist de verificaciones obligatorias por gate como conjunto de ejecutores/artefactos y criterios observables; el componente que crea recibos debe ejecutar los comandos reales de manera controlada y derivar PASS de sus resultados. Exigir la cobertura completa del catálogo y tests negativos ante ausencia de un subcontrol o salida vacía/incorrecta. No duplicar las 26 puertas.

**QA-RC-02f — P2, el colector aún carece de generación integrada de recibos fiables.** El código actual contiene `leer_recibo` y `colectar`, pero no expone en su CLI una fase que ejecute `GATE_VERIFICADORES` y escriba todos los `<QG>.recibo.json` a partir de resultados observados; el agente promete hacerlo en sesión siguiente. Los recibos pueden provenir de un ejecutor externo si este es verificable y el contrato está definido, pero un script que escriba PASS/exit=0 sin invocar verificadores **no cumple QA**. Mantenerlos fuera del árbol del SHA candidato para evitar circularidad.

## QA-RC-05 y entrega final

**QA-RC-05a — P2, recorrido no reproducible desde el repo.** Incorporar al árbol el harness R07 exacto (sin rutas/secretos reales), o entregar su código reproducible mediante artefacto inmutable accesible; instrumentar resultados por paso, hash de la **nota normalizada efectiva** (después de `vault_write`), cuarentenas detectadas por run ID (no por conteos absolutos), y protocolo JSON-RPC secuencial `initialize → notifications/initialized → tools/list → tools/call`. Exigir realmente 19/19 casos o explicar criterios que determinen caso no aplicable; no maquillar 15–16/19 como PASS. Añadir prueba de contenido tras restauración y el vínculo con wheel/SDist construidos desde el SHA final.

**Arquitectura — decisión del propietario:** preferible eliminar cinco cruces mediante composición legítima cuando sea posible. Cualquier cambio a `permanente` requiere autorización explícita, dueño, plazo/revisión, riesgo y tratamiento en QG-01; **no se ratifica automáticamente**. No modificar baseline por cosmética.

**Secuencia de cierre recomendada:** 1) obtener y registrar resultado final de las puertas y la suite actuales (no declararlos verdes sin leer su salida); 2) reparar QA-RC-02d/e y generar tests de regresión; 3) terminar/publicar y ejecutar R07 19/19 sobre wheel instalada; 4) decidir arquitectura o mantener pendiente; 5) publicar SHA nuevo, rehacer controles afectados y generar recibos **fuera** del árbol; 6) acreditar QG-00..06 con subchecks observables; 7) QG-07 BLOCKED hasta CI concluida; 8) solicitar nueva QA independiente y autorización de merge.

**Estado formal:** `QA_REQUIRES_CHANGES`, `QA-RC-01f=ACCEPTED_SCOPED`, `QA-RC-02=PARTIAL`, `QA-RC-03=OWNER_DECISION_PENDING`, `QA-RC-05=INCOMPLETE/UNREPRODUCIBLE_FROM_GIT`, `QG-07=BLOCKED`. **No fusionar PR #1/#2/#3, no actualizar `main`, no reescribir historia pública, no divulgar identificadores privados.**

