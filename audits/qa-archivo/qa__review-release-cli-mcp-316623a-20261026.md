# Archivo: `qa/review-release-cli-mcp-316623a-20261026`

- Commit(s) sobre la rama de trabajo:
  - `defc657a7771378ffa61a9af62b4767c7f41b987` 2026-10-26 — docs(qa): dictamen R11 HEAD 316623a, logs CI y pendientes release
- Base: `316623a2b3ceebcd72665639e2b54b8edff6f098`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-316623a-20261026`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R11, freeze 36c91e0 / HEAD 316623a (2026-10-26)

**Rama del ejecutor:** `work/release-cli-mcp-20261025`  
**SHA congelado de pruebas:** `36c91e0bc231171e8fd45efbe847f894459fa96d`  
**HEAD documental actual revisado:** `316623a2b3ceebcd72665639e2b54b8edff6f098`  
**SHA del E2E instalado:** `0241ffe8d64ff1ac52d0075d8112b42596dc6713`  
**Rama de QA independiente:** `qa/review-release-cli-mcp-316623a-20261026`  
**Método:** lectura directa del repositorio, PR, archivos, diffs y logs completos de los jobs GitHub Actions fallidos. **QA no ejecutó localmente pytest ni la wheel**; se distingue explícitamente evidencia reportada por el ejecutor de comprobaciones independientes.

## Veredicto

**QA_REQUIRES_CHANGES — RELEASE NO AUTORIZADO.** El avance de producto se reconoce: el agente reportó suite `6307 passed / 13 skipped / 0 failed` y `26/26` sobre `36c91e0`; E2E `27/27` desde wheel sobre `0241ffe`. El diff `0241ffe→36c91e0` solo añade documentación y pruebas/herramental de auditoría, no código de la wheel; `36c91e0→316623a` únicamente toca el informe de readiness y los buzones de QA/handoff. Eso respalda la distinción entre freeze técnico y HEAD documental, pero no reemplaza verificar artefactos y procedencia.

### Hallazgo QA-REL-01 — P1: ocho jobs CI fallidos, NO es solo bloqueo de cuenta

**Evidencia independiente del run `40299732445` del SHA `36c91e0`:** 25 jobs, 9 `completed/success`, 8 `completed/failure`, 8 `queued`, ninguno finalizado globalmente. **Los ocho fallos ocurren en el paso `Run unit tests` de `Validate Vault Spec`**, incluidos Windows 3.9/3.10/3.11/3.12 y Ubuntu 3.9/3.10/3.11/3.12. Los logs devolvieron, por ejemplo, **18 failed / 6288 passed / 12 skipped** para Ubuntu Python 3.11; **20 failed / 6287 passed / 13 skipped** para Windows Python 3.12 y **22 failed / 6282 passed / 16 skipped** para Windows Python 3.9. Estas cifras son reales del runner y no contradicen la suite local verde: miden entornos/procedencias distintos.

**Causa raíz fuertemente sustentada de la mayoría de fallos:** el checkout de CI ejecuta `git fetch ... --depth=1` (visible en logs). El archivo `.github/workflows/vault-ci.yml` usa `actions/checkout@v4` sin `fetch-depth: 0`. Las pruebas `test_changelog_check`, `test_contrato_nota`, `test_metricas`, `test_fase2_hf201_privacidad` y otras usan `git show`, `git cat-file` y referencias históricas; sus commits (`6ddf04e`, `974c2ba`, `8f24030`, `44f6f89`, `32d2561`) **SÍ existen** en el repositorio remoto, verificados directamente por esta QA. En checkout superficial no están disponibles. El plano `docs/BLUEPRINT.md` también deriva información del historial. **Primer experimento:** `fetch-depth: 0` en el checkout de los jobs consumidores de historia, comparar casos focalizados y luego totalidad; preservar tests y baselines. Si algunos fallos persisten, investigar separadamente en lugar de atribuirlos todos a esta causa.

**Otros defectos/ambientes que sí aparecen en los logs:** el test real `tests/test_mcp_runner.py::test_la_tool_por_modulo_se_ejecuta_por_mcp` recibe `TOOL_EXECUTION_FAILED` porque el Python hijo no dispone de `yaml` (`ModuleNotFoundError: No module named 'yaml'`); probar selección de intérprete `VAULT_MCP_PYTHON`, instalación y prueba E2E desde wheel. Windows 3.9 también reporta fallo de inicialización de aleatoriedad del proceso Python (`_Py_HashRandomization_Init`) y error en portabilidad UTF-8; investigar como hechos separados. No atribuir automáticamente toda falla a checkout superficial.

**El run del HEAD documental `40308451152`** sigue no concluido: 9 jobs completados con éxito, 8 en progreso y 8 en cola al revisar. Así, runners de GitHub **sí están ejecutando trabajos**; la tesis anterior `CI bloqueada permanentemente por cuenta/billing` en `CI-diagnostico.md` y `INFORME-READINESS-TERCEROS.md` quedó **refutada en su forma categórica**. No pedir al propietario cambiar facturación como primera acción. Primero corregir CI y recibir conclusiones verificables de los 25 jobs del SHA nuevo.

### Hallazgo QA-REL-02 — P1: readiness/protocolo insuficientemente reconciliados

`audits/fase2/INFORME-READINESS-TERCEROS.md` conserva en su cabecera `HEAD=0241ffe` pese a que la rama alcanzó `316623a`; su sección 9 sí registra freeze `36c91e0`. El `PROTOCOLO-QA.md` menciona `HEAD=ee7e64a` y freeze `36c91e0`, pero también usa autorías de QG no idénticas a `catalogo-qg.yaml`: **QG-01** es propiedad de `meta_toolkit - vault_arch`, **QG-02** de `gobernanza - vault_norms`, **QG-04** requiere aceptación `QA arquitectónico + propietario`, y **QG-07** es QA verifica/propietario autoriza. `PROTOCOLO-QA.md` asigna QG-01/QG-02/QG-04 genéricamente al ejecutor y omite al propietario de QG-04. Fuente de verdad: `catalogo-qg.yaml`; el protocolo debe derivarse de ella, no proponer atribuciones distintas.

`INFORME-READINESS-TERCEROS.md` presenta `usable por terceros técnicos hoy` y `release 1.0` pese a QG bloqueados, ausencia de aprobación y falta de evidencia multiplataforma; distinguir **prueba controlada desde wheel en Windows** de **distribución o soporte público autorizado**. Los PRD `docs/product/prd-cli.md` y `docs/product/prd-mcp.md` siguen declarando versión target `v1.0`, listas incompletas y número MCP `116/117`, mientras el paquete declara `41.23` y el recorrido E2E enumera **97 tools**. Se necesita matriz contrato-versión-capacidades (AS-IS vs promesa), decisión de versión/tag/canal y rectificación de docs derivados, sin atribuir funciones no ejercitadas.

### Hallazgo QA-REL-03 — P1: QG-00, QG-01, QG-02 no están listos y no son eximibles unilateralmente

- `QG-00/01`: reconciliador mantiene diez divergencias históricas vinculadas a cinco cruces off-port vigentes; **no aceptado** por el propietario. Se recomienda evaluar alternativa **B** (migración compatible hacia puerto) con evidencia de impacto y rollback; la ratificación o excepción formal es decisión del propietario. No silenciar inventarios ni modificar baselines para obtener verde.
- `QG-02`: 14 hallazgos del sandbox canónico (13 de contenido documental y uno de contención AP-36 sobre backups externos) siguen sin cierre. AP-39 está reportado como corregido y re-auditado en runtime limpio: verificar procedencia completa en QA. El propietario debe decidir la política de certificación; **certificar el runtime limpio no borra los hallazgos reales del sandbox**. Corregir contenido documental bajo control sin reescribir datos históricos y no borrar backups externos sin consentimiento.
- `QG-03..06` tienen recibos locales reportados PASS, pero permanecen `BLOCKED` como gates finales mientras QG-00 no pase.
- `QG-07` carece de CI concluyente, tiene fallos explícitos en un run del freeze, y no cuenta con autorización del propietario. **No fusionar ni publicar release.**

### Hallazgo QA-REL-04 — P2: artefactos de release, evidencia y estado del GOAL

La wheel/sdist fue reconstruida y ejecutada en un entorno de tercero para `0241ffe` (reportado 27/27). Las pruebas finales sobre `36c91e0` (reportado 6307/13/0 y 26/26) son valiosas, pero todavía faltan evidencias accesibles, inmutables, con hash completo del artefacto y JUnit/exits manifiestos por SHA y el resultado real de CI. No es aceptable usar un `HEAD` posterior sin dejar documentado el diff y por qué no invalida el artefacto. Emitir `release-manifest` con `source_sha`, `tree_sha`, `package_sha256`, `junit_sha256`, `ci_run_id`, versiones soportadas **acreditadas**, conclusiones, QA y decisión del propietario. No crear un tag/release real antes de autorización.

### Siguiente orden técnica recomendada

1. Investigar y corregir fallas CI *reales*: checkout profundo para historia, MCP/PyYAML/selección de Python y otros fallos Windows, sin eliminar tests ni modificar aserciones para verde.
2. Ejecutar los casos focalizados fallidos en CI, conservar logs y exit codes; entonces re-ejecutar los 25 jobs del nuevo SHA (no reutilizar el run fallido).
3. Reconciliar `CI-diagnostico.md`, `INFORME-READINESS-TERCEROS.md`, `PROTOCOLO-QA.md` y los PRD para eliminar contradicciones de identidad, capacidades, versión, autoridad y compatibilidad.
4. Completar acciones técnicas posibles para QG-02 (documentos) y preparar decisiones del propietario sobre arquitectura B y contrato de certificación sin dar por ratificadas decisiones abiertas.
5. Publicar un candidato nuevo, congelar el SHA, generar recibos contemporáneos, auditar la wheel/CI y solicitar QA independiente. La última autoridad del release es exclusiva del propietario.

**Estado formal:** `QA_REQUIRES_CHANGES`; `RELEASE_NOT_AUTHORIZED`; `QG-07=BLOCKED`; `CI_FAILED_JOBS_PRESENT`; `OWNER_DECISIONS_PENDING`; `CONSTITUTION=DRAFT`. Mantener `main` intacta, PR #3 DRAFT, sin force-push, reescritura de historia ni operaciones sobre datos reales sin autorización.

