# Archivo: `qa/review-release-cli-mcp-76669e4-20261026`

- Commit(s) sobre la rama de trabajo:
  - `223e2d36b59022abe74b5cff669bf15539df3ee2` 2026-10-26 — docs(qa): R13 CI 25/25 verificada, estado real release y acciones correctivas
- Base: `76669e4bab4a09b3eb90d61f6e3b55cf5b375447`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-76669e4-20261026`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R13 / candidato CLI+MCP (2026-10-26)

**Rama de revisión:** `qa/review-release-cli-mcp-76669e4-20261026` (creada a partir de HEAD de trabajo).  
**HEAD documental revisado:** `76669e4bab4a09b3eb90d61f6e3b55cf5b375447`.  
**SHA de producto con CI demostrada:** `e198ffb3477dc4f9c870bb5176fe99f43b0fb810`.  
**CI acreditada independientemente:** run `40430269201`, `completed/success`, **25/25 jobs `completed/success`**: 12 `Validate Vault Spec` (Windows, Ubuntu, macOS × Python 3.9–3.12), 12 `Product gates (wheel)` para misma matriz, 1 `Lint Python`. Vista de jobs: GitHub Actions API.  
**Método:** revisión de GitHub en código, manifiestos, documentos, contratos QG y estados CI; no ejecución propia de pytest, gates ni wheel. Los **6330 passed/13 skipped/0 failed**, 26/26 y E2E 27/27 constan en el informe del ejecutor y se deben cotejar contra artefactos originales completos, hash y SHA, sin atribuirlos como tests ejecutados por QA.

## Veredicto

**QA_TECNICA_CI_VERIFICADA / RELEASE_BLOCKED / QA_REQUIRES_OWNER_DECISIONS**.

Esta revisión **reconoce la corrección y ejecución exitosa de CI del candidato `e198ffb`**; queda superado el diagnóstico anterior de bloqueo de cuenta, checkout superficial, PyYAML y fallos en macOS **para ese SHA**. No son pendientes de ingeniería repetibles mientras no se detecten regresiones nuevas.

**NO se aprueba el release**: `QG-00` y `QG-01` continúan sin acreditación por 10 divergencias; `QG-02` continúa bloqueada por el contrato de certificación del sandbox y el `vault-backups` externo (AP-36). Por la política `audits/fase2/politica_qg.py`, la conclusión del run CI `success` NO sustituye `QG-07=PASS` como decisión global; la evaluación final debe dejar `QG-07=BLOCKED`, `liberable=false` hasta QG-00..06. Distinguir explícitamente **subcheck de CI PASS** de **decisión QG-07 BLOCKED**.

## Acciones para el ejecutor, acotadas y compatibles

**QA-REL-01 — P1 / reconciliación arquitectónica y autorización.** Mantener las 10 `DIV-01..10` sin aceptación ficticia y los cinco cruces como `a_eliminar`, con dueños, plazos y riesgo. Presentar al propietario la alternativa **B compatible** de `audits/architecture/PLAN-B-MIGRACION-CRUZES.md`, con A como destino. Su criterio `§6.1` (independencia semántica, operacional, de resultados y efectos) es esencial: sustituir imports por `subprocess` sin frontera real NO cierra la deuda. Sin ratificación: preparar plan/tests en aislamiento sin mutar contratos ni baselines, conservar QG-00/01 BLOCKED. Tras aprobación: ejecutar B con equivalencia CLI/MCP, wheel instalada fuera de checkout, sin ocultar dependencias, nueva medición del grafo y reconciliación legítima; no forzar `PASS` retocando el snapshot.

**QA-REL-02 — P1 / QG-02 y AP-36.** Contrastar escenario A (sandbox canónico) con escenario B (runtime limpio creado por el producto); elegir el sujeto normativo del control requiere autoridad de propietario si modifica la política. `vault-backups` fuera del vault es un hallazgo de contención real, no algo que se exonera por cambiar el entorno. Inventariar contenido, titularidad, creador, ruta, hashes, impacto y reversibilidad; proponer preservar/mover/quarantena externa/no tocar, SIN purgar ni mover datos ajenos sin aprobación. Confirmar que el comportamiento actual del producto NO genera efectos fuera de raíz; separar residuo histórico del side-effect nuevo, registrar ambas mediciones. No bajar AP-36, falsificar evidencia ni dar QG-02 PASS unilateralmente.

**QA-REL-03 — P1 / identidad exacta del release.** GitHub comparó `e198ffb...76669e4`: **un commit posterior documental** (informe readiness, protocolo QA, diagnóstico CI y buzón ejecutor). Conservar por separado `product_sha=e198ffb`, `documentation_sha=76669e4`, `artifact_sha256`, `junit_sha256`, `ci_run_id`, los recibos por subcheck y SHA de sus verificadores. QG-00 exige evidencia del SHA declarado y árbol limpio; si se pretende certificar `76669e4` como release candidate completo, ejecutar la validación/CI correspondiente a ese SHA o demostrar mediante una política **existente y ratificada** cómo se conserva identidad y se invalidan controles. **No afirmar que el éxito de CI `e198ffb` prueba automáticamente `76669e4`.** No reempacar con hashes nuevos y llamarlos idénticos: un wheel ZIP puede tener timestamps distintos; usar manifiesto de contenidos 706/706 más hashes específicos por build.

**QA-REL-04 — P2 / consistencia de documentación.** `INFORME-READINESS-TERCEROS.md` todavía lleva cabecera R12/408eb23 mientras §9 ya documenta R13 y `e198ffb`; en §7 contiene un riesgo anticuado "macOS sin medir" cuando la matriz ya aprobó macOS. Reconciliar estados y fechas contra evidencias originales, corregir `CI-diagnostico.md`, `PROTOCOLO-QA.md`, matriz de capacidad y PRD obsoletos (126 tools catálogo, 97 expuestas MCP, 14 perfil agente; distinguir declaración, test y documentación). Conservar histórico como histórico, no borrarlo. Añadir a `INFORME-READINESS-TERCEROS.md` una **matriz de release** con etapas, norma, criterio, evidencia por SHA, estado, dueño, acciones negativas/correctivas, y autoridad.

**QA-REL-05 — P2 / QA final y pruebas eficientes.** Mantener la suite completa, 26 puertas y E2E como certificación obligatoria, pero no repetir 6k+ pruebas tras cada cambio documental. L0/L1 tests focalizados y validación semántica, L2 integración por impacto, L3 final SHA congelado en fuente inmutable. Ante `FAIL`, categorizar defecto de producto/test/fixture/CI/norma, conservar logs y reproducir un test aislado y un negativo antes de volver a L3. Ante `BLOCKED` no forzar PASS. Ante `NOT_RUN` generar evidencia real antes de acreditar. Ante CI fallida mirar jobs y logs, no atribuir billing. Ante fuga o pérdida de datos detener publicación y preservar originales.

## Puertas y propiedad de decisión

- **QG-00/01:** no aprobadas hasta arquitectura reconciliada legítimamente o excepción exactamente autorizada por la política. `QG-00` no admite waiver de identidad.
- **QG-02:** no aprobada hasta ejecutar el contrato normativo ratificado de gobernanza sin violaciones de contención ni controles degradados.
- **QG-03..06:** los recibos individuales constan PASS según informe del ejecutor, pero **efectivamente BLOCKED** por prerrequisito QG-00.
- **CI para `e198ffb`: PASS verificado en GitHub (25/25)**.
- **QG-07 decisión global: BLOCKED** aunque CI PASS mientras existan QG previos bloqueados.
- **Ratificación:** propietario decide Constitución DRAFT, arquitectura A/B/C, sujeto normativo de QG-02, destino de backups externos y liberación/versión. QA no sustituye autorización final.

**Resultado de esta revisión:** `CI_VERIFIED=YES (e198ffb)`, `RELEASE_AUTHORIZED=NO`, `MAIN_UNCHANGED`, `PR3_DRAFT`, `OWNER_DECISION_REQUIRED`. La ejecución puede continuar sin bloqueos técnicos ficticios ni cambios destructivos; antes de un nuevo dictamen final publicar manifiesto de release/capacidad/decisiones sobre SHA exacto, evidencia y veredicto global del colector. **NO MERGE, NO RELEASE, NO FALSE PASS.**

