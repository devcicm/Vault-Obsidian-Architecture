# Acta de relevo QA — R22 / continuidad de release CLI + MCP

**Fecha local de referencia:** 2026-10-27 (las ejecuciones GitHub reportan horas UTC del 2026-10-28).  
**Estado:** HANDOFF_PENDING_SUCCESSOR_ACK — la sucesión de funciones QA requiere designación explícita del propietario.  
**Fuente:** inspección estática GitHub de repositorio, PR, ramas, código R22, protocolo, manifiesto, buzón y resultados de GitHub Actions. **No se han ejecutado las pruebas locales ni se ha inspeccionado el filesystem del agente.**  
**Rama donde se publica esta acta:** `qa/handoff-r22-2f5bd1b-20261027`, aislada de la ejecución y de main.  
**Commit fuente congelado para el acta:** `2f5bd1b96938e31c861b26a228c7e4c718ba72eb`.  
**Destino de lectura de sucesor:** este archivo + `audits/handoff/RESPUESTA-QA.md` en esta misma rama.

## 1. Veredicto de relevo (NO autorización de release)

**R22: implementación del puerto y migración B publicada; CI de los dos SHAs relevantes verde 25/25; certificación global y autorización de release NO concedidas.** El estado formal es `RELEASE_BLOCKED / GOAL_OPEN / QA_SUCCESSOR_PENDING`.

Las evidencias del ejecutor son útiles pero no sustituyen el dictamen formal: suite `6440 passed / 14 skipped / 0 failed`, puertas `26/26`, E2E `27/27`, wheel `1afe8a0ff01474b3332e0f671bd09fd4f582e25ad3d30f45c9f4112a5bf90764`, sdist `9fccc2ebfe312fee744c4030d3d6e2f96eec60bd7f606910bc3c9ab87af23a34`. **Reportado desde archivos del ejecutor**, no repetido localmente por QA. GitHub Actions sí se verificó mediante respuesta real de los jobs.

### Identidades y evidencias por commit

| Rol | SHA | Estado comprobado |
|---|---|---|
| Producto anterior | `015b7765b80cac21c6dcf859ae075d036cd01def` | Evidencia histórica R14, NO trasladable |
| Código certificado por ejecutor R22 | `81ab2ff8caccc88e1364373094351f79dc7004cb` | CI run `40611205349` = completed/success, 25/25 jobs completed/success; suite y E2E reportados |
| HEAD documental posterior | `3d332a531269cdb9587c22f8f29eb01d9a077c4d` | CI run `40615607289` = completed/success, 25/25 |
| HEAD ejecutor al relevo | `2f5bd1b96938e31c861b26a228c7e4c718ba72eb` | Solo `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` cambió respecto a 3d332a5; run `40620231867` en progreso, sin conclusión al consultar; **no contarlo verde** |
| main remoto | `1c34754258441550139ce895e182ab219c93f9bb` | Sin merge, no cambiado |

**Comparación Git:** `81ab2ff..2f5bd1b` consta de DOS commits y solo cambia `audits/fase2/CANDIDATO-RELEASE.yaml` y `audits/handoff/RESPUESTA-DEL-EJECUTOR.md`. Este hecho respalda identidad de código sin cambios empaquetables, pero los digest binarios deben conservar su procedencia.

### Gobierno QG del candidato R22 (según manifiesto publicado)

| Control | Estado al relevo | Motivo/acción |
|---|---|---|
| QG-00 | BLOCKED | DIV-01..10 sin acto ni snapshot reconciliado formalmente |
| QG-01 | BLOCKED | Igual; `off_port_total=0` NO equivale a firma de divergencias |
| QG-02 | BLOCKED | DEC-03 (contrato C) y DEC-04 (residuo externo AP-36) pendientes |
| QG-03 | NOT_RUN | Recibos del candidato R22 aún no emitidos; previos pertenecen a otro SHA |
| QG-04 | NOT_RUN | Igual |
| QG-05 | NOT_RUN | Igual |
| QG-06 | NOT_RUN | Igual |
| QG-07 | BLOCKED | Requisitos anteriores y decisión del propietario, aunque CI del código esté verde |

`TEST_PASS ≠ CI_PASS ≠ QG_PASS ≠ QA_APPROVED ≠ OWNER_AUTHORIZED ≠ PUBLISHED`.

## 2. Qué hizo R22 y qué falta

- **Hecho:** `vault/kernel/controles.py` publica el contrato de datos+proceso AP-40/42/43; `vault_mcp_catalog --check-params`, `vault_smoke --baseline-check`, `vault_voice --coverage`; fachada de gobernanza migra al puerto. Ejecutante reporta `off_port_total 5→0`, `crossings_sites 49→46`, pares `23→22`; audit alrededor de 2–3 s, con presupuesto 5 s. La comparación está respaldada por código y CI, pero QA no volvió a correr microbenchmarks.
- **P1 abierto I2-a:** `empaquetado/fuera-de-la-wheel.json` todavía excluye `vault_smoke` y `vault_voice`. Una instalación desde wheel limpia NO dispone de esa superficie de mantenimiento; el puerto retorna `no_ejecutado` de forma segura. Publicar entry point y `maintenance_publicada`, definir paquete y dependencias reales, verificar AP-40/42/43 desde **wheel externa**, con resultados ejecutados y cobertura completa; implica **nuevo candidato, rebuild, E2E, suite, 26 gates, CI y recibos**. Evitar declarar 27/27 del E2E existente como prueba de estos tres controles si ese recorrido no los ejecuta.
- **Snapshot:** diez fichas DIV-01..10 siguen sin ratificación; reconciliador exit 0 y off_port=0 son controles distintos de una reconciliación histórica formal. No cambiar `ratificado` ni re-tomar snapshot sin decisión.
- **Par residual:** `gobernanza -> meta_toolkit` vía `vault/gobernanza/tool.py -> catalog_adapter` permanece declarado `a_eliminar` fuera de los cinco sitios de la ronda.
- **DEC-01..06:** no hay acto del propietario firmado ni autorización. La preferencia B/C está documentada como propuesta **no ratificada**. La migración B ya implementada técnicamente no debe tratarse como autorización retroactiva; propietario decidirá alcance y aceptación.
- **DEC-04:** `vault-backups` externo = 66 archivos, 854108 bytes según inventario del ejecutor, **no confirmado físicamente por QA**. No borrar, comprimir, mover, renombrar ni purgar sin acto separado.
- **Historia:** no reescribir Git ni forzar push; ningún reporte de privacidad implica ausencia universal de secretos.

## 3. Riesgos de handoff y contradicciones de documentación

1. `audits/handoff/PROTOCOLO-QA.md` tiene sección «solicitud abierta» anclada a R14/`015b776` y llama ACTIVA a una rama QA de R12. Es histórico, **no es el estado vigente**. El nuevo agente de ramas debe documentar la sucesión R22 de forma aditiva sin falsificar veredictos pasados.
2. `audits/fase2/CANDIDATO-RELEASE.yaml` apunta correctamente a producto `81ab2ff`, CI 25/25, y QG-03..06 NOT_RUN; la cabecera dice aún «candidato a44ead4». Actualizar descripción y vínculo de identidad sin modificar `product_sha` ni digests.
3. `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` conserva secciones intermedias «CI: sin conclusión» y «SHA a44ead4», posteriormente supersedidas por las evidencias R22 del SHA `81ab2ff`. Añadir índice `estado_actual` vs `histórico`; nunca reescribir la evidencia antigua.
4. Parche local de worktree retirado: `%TEMP%\opencode\wt-r1b-iso-20261025.patch` (~133 KB), **solo reportado** por el agente; QA no comprobó su existencia, integridad ni contenido. Antes de transferir el entorno verificar localmente que existe, calcular SHA-256, preservar copia en destino seguro con permisos apropiados y comprobar que no contiene secretos; no publicar el parche ni eliminarlo por rutina.
5. El ejecutor informó `worktree remove --force` de tres worktrees antiguos. QA solo verificó referencias remotas; **no puede confirmar** estado del filesystem local, stash, backup local ni worktrees. Ninguna eliminación adicional es parte de este acta.

## 4. Inventario de ramas remotas a fecha del acta

No se han borrado, movido, renombrado, fusionado ni forzado refs.

### Ramas generales y auxiliares

| Rama | SHA observado | Política |
|---|---|---|
| `audit/archify-governance-20261024` | `ef77a7b19a6a` | PR #1 OPEN histórico |
| `fase2/deuda-y-product-readiness-20261025` | `84f7c298b008` | PR #2 DRAFT histórico |
| `main` | `1c3475425844` | Base protegida por política de trabajo; remoto intacto |
| `proposal/dec-02b-dec-03c-dec-04pending-20261026` | `cc05eab1e1ba` | Propuesta consultiva sin ratificación |
| `work/release-cli-mcp-20261025` | `2f5bd1b96938` | Ejecución actual, PR #3 DRAFT |

### Ramas de auditoría QA (históricas)

| Rama | HEAD observado | Política |
|---|---|---|
| `qa/handoff-r22-2f5bd1b-20261027` | `2f5bd1b96938` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-arquitectura-trazabilidad-e8f7aea-20261025` | `9919c57e9ad8` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-authority-r20-e0d0c75-20261027` | `e5220ffc62ab` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-authority-r21-4bf4092-20261027` | `2d00db418e17` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-4c66fc2-20261025` | `1e75d94d007d` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-09e849c-20261027` | `7d2679ab739f` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-015b776-20261027` | `e47d62f0135c` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-29c1a15-20261025` | `a9e0143b5e24` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-408eb23-20261026` | `e30e6686a560` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-0580b7e-20261025` | `5de279a500c2` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-2054e8d-20261027` | `8be11d312b93` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-4595aea-20261025` | `f7100898d9dd` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-76669e4-20261026` | `223e2d36b590` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-316623a-20261026` | `defc657a7771` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-4396273-20261025` | `8dbd5b0d0050` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-5836474-20261025` | `fabe442765ca` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-ab2e30c-20261027` | `222094f666b1` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-b4f7302-20261027` | `2369be8199d6` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-bfca45a-20261025` | `628df53afc8e` | Histórico QA, lectura y custodia; no borrar ni fusionar |
| `qa/review-release-cli-mcp-e198ffb-20261026` | `7dc1a254b1f9` | Histórico QA, lectura y custodia; no borrar ni fusionar |

**Manejo recomendado:** conservar todas las QA como archivo de dictámenes por commit; NO fusionarlas a main ni copiarlas a la rama del ejecutor; clasificar `ACTIVA` por el **último dictamen pertinente**, no por el nombre o por el campo antiguo del protocolo. Cualquier archivado, borrado o consolidación de ramas históricas requiere autorización del propietario y plan de preservación de referencias.

## 5. PR y garantías de Git

| PR | Estado GitHub | Tratamiento |
|---|---|---|
| #1 audit/archify-governance-20261024 | OPEN, no draft, no merge | histórico; leer dependencias y conservar |
| #2 fase2/deuda-y-product-readiness-20261025 | OPEN/DRAFT, no merge | histórico; conservar |
| #3 work/release-cli-mcp-20261025 | OPEN/DRAFT, no merge | único PR candidato, NO aprobar ni fusionar |

El remoto `main` sigue `1c34754258441550139ce895e182ab219c93f9bb`. El ejecutor informa tres commits locales de `main` sin publicar y un `stash@{0}`: son **datos locales no comprobables con GitHub**; el agente de ramas DEBE verificar `git reflog`, `git stash list`, `git branch -vv`, `git worktree list --porcelain`, backups y `git fsck --no-reflogs` (lectura, sin alterar refs), antes de realizar acciones que afecten referencias. No hacer `git gc --prune`, `reset --hard`, `clean -fdx`, `worktree remove --force`, `branch -D`, `push --force`.

## 6. Protocolo de relevo del nuevo agente QA

**La designación de una nueva autoridad QA la hace únicamente el propietario.** Esta acta no transfiere permisos ni implica que cualquier agente pueda aprobar o firmar.

1. Reconocer el mismo catálogo de autoridad real `catalogo-qg.yaml` y su política; protocolo documental sin poder de autoautorizar cambios.
2. Leer acta, último dictamen anterior `qa/review-authority-r21-4bf4092-20261027` (`2d00db418e1764f8ea99834da30efc0af18050b7`), el manifiesto, decisiones, PR y runs de CI.
3. Desambiguar **candidato de código** (81ab2ff), **HEAD documental** (3d332a5) y **HEAD de rama** (2f5bd1b); nueva implementación I2-a crea nuevo SHA candidato, no migra evidencia de R22 automáticamente.
4. Recibir inventario ordenado de acciones pendientes del ejecutor, no aprobarlas solo por número de tests.
5. Revisar R22 de forma independiente (evidencia primaria, diffs, contratos, CI), documentar limitaciones de acceso; pedir remediación si encuentra bloqueantes.
6. Emitir dictámenes solo en rama QA **nueva y aislada** con convención `qa/review-<ambito>-<sha>-<fecha>`; mantener buzón `RESPUESTA-QA.md` de solo lectura para ejecutor; no editar `main` ni work.
7. No asumir que el nuevo QA ejecutó 6440 tests; si solo lee logs, decirlo. Prohibido certificar sin evidencias válidas.
8. Pedir firma/acto real para DEC-01..06; no autorizar waivers ni purga de datos.

## 7. Secuencia recomendada para agente de ramas + ejecución siguiente

**Primero Git/documentación (sin código):**
- Confirmar estado remoto, upstream, HEAD, PRs, worktrees, stash, reflog, patch y base local `main`; preparar inventario verificable `rama → SHA → dueño → PR → autoridad → destino → riesgo`.
- Preservar todo; generar informe y corregir referencias actuales en **rama ejecutora** mediante commit exclusivamente documental con validación dirigida. NO crear un merge.
- Etiquetar históricas como históricas **solo en el índice documental**, no cambiar nombres ni borrar ramas.
- No adjudicarse autoridad QA. Pasar acta al siguiente agente autorizado.

**Después ejecución técnica (solo con alcance habilitado):**
- Proponer plan I2-a detallando empaquetado, entry points, API/CLI, checks en wheel limpia, seguridad, latencia, rollback, pruebas negativas y cambio de SHA.
- Implementar I2-a únicamente dentro de la autorización vigente o pedir acto expreso por afectar DEC-02. No inferir ratificación de la preferencia B/C.
- Tras modificar código empaquetado, generar SHA nuevo y ejecutar 26 puertas, suite completa, E2E ampliado para AP-40/42/43 desde wheel, CI 25/25 y recibos QG nuevos por subcheck. Nada de auto-PASS.
- Reconciliar DIV-01..10 bajo decisión del propietario, contrato C de QG-02 bajo decisión, custodiar AP-36 sin tocar backups.
- Solicitar QA independiente del nuevo candidato; QG-07 y REL-08/09 siguen BLOCKED hasta cumplir todo.
- Solo propietario autoriza merge/tag/release.

**Estado final de esta acta:** `QA_HANDOFF_PREPARED`, `SUCCESSOR_NOT_YET_DESIGNATED`, `R22_TECHNICAL_EVIDENCE_PRESENT`, `I2A_OPEN`, `OWNER_DECISIONS_OPEN`, `RELEASE_BLOCKED`, `MAIN_UNCHANGED`. 
