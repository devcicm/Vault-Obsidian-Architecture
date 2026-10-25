# Estado del release candidate — GOAL CLI + MCP para terceros

**Fecha:** 2026-10-25
**Rama de trabajo:** `work/release-cli-mcp-20261025`
**SHA base:** `84f7c298b008b482118b592ba77255b8de805f44` (fase 2 + dictamen QA)
**Estado:** **READY_FOR_APPROVAL** (producto técnicamente verificado; CI y QG de
release bloqueados por causas externas y por evidencia aún no atribuible al SHA)

---

## Lo implementado en esta ronda

| Unidad | Commit | Qué |
|---|---|---|
| TD-0008 | `cc85491` | `vault_init --clean` transaccional: preflight, `--confirm`, `--dry-run`, cuarentena hermana, verificación por sha256, rollback, purga diferida, symlinks no atravesados, `.locks` preservado. 14 pruebas. |
| TD-0003 | `51b5cd1` | Estados reales de AP-40/42/43 (`ejecutado/degradado/fallido/no_ejecutado`), `checks[]` + `completo` aditivos, CLI `--strict` fail-closed. 15 pruebas. |
| GOAL C | `f952169` | `audits/fase2/colector_qg.py`: acredita SHA en git, existencia/ contenido/procedencia de evidencias, control de ejecución real, suite por JUnit + recibo, CI por `head_sha` y `success`. 19 pruebas. |
| GOAL D/F | `ff24179` | Diagnóstico de CI (bloqueo de cuenta, no del workflow) y recorrido real de tercero sobre la wheel; Quick Start corregido. |
| Q04–Q07 | `667a6a5` | Inversión: el motor empaquetado deja de importar `vault_smoke`/`vault_voice`/`vault_mcp_catalog`; la composición pasa a `vault_norms` (mantenimiento, fuera de la wheel). `shipped_imports_of_excluded: []`. |
| Q04–Q07 | `59d0465` | El cruce declarado se reubica en el registro de arquitectura (5 entradas, sin crecer). |
| Regresiones | `3a10dc0` | Anotaciones diferidas (`from __future__`), detector AP-56, `test_catalog_params` sobre la fachada y baseline de rutas que **encoge** de 177 a 175. |

## Verificación

| Comprobación | Resultado |
|---|---|
| 26 puertas | **26/26 en verde** |
| Suite completa | **6250 passed, 13 skipped, 0 failed** (991 s) |
| `vault_arch --check --strict` | ok, `new_off_port_crossings: []`, `off_port_total: 5`, baseline 5 (sin crecer) |
| `vault_servicio --check --strict` | ok, `shipped_imports_of_excluded: []` |
| `vault_error_contract --check --strict` | ok (nuevo código `INIT_FAILED_AFTER_CLEAN` en el catálogo) |
| `comprobar_saneamiento` | exit 0 |
| Wheel | 706 ficheros, 2 `.mjs`, sin trazas ni tests; sha256 `d80c4974…a2b5` |
| Sdist | sha256 `1b7c81eb…74a9` |
| `pip-audit` | sin vulnerabilidades conocidas (PyYAML) |
| MVP tercero | init, doctor, status, escritura/lectura CLI, MCP 97 tools, lectura y búsqueda por MCP, persistencia tras reiniciar, backup y restore de 79 ficheros |
| Seguridad MCP | traversal rechazado, args incompletos y tool inexistente con error controlado |

## Quality Gates

| QG | Estado | Motivo |
|---|---|---|
| QG-00 | BLOCKED | Falta evidencia regenerada y atribuible al SHA del RC (OBS-R06-01); el colector la exige y la rechaza si no lo menciona |
| QG-01 | BLOCKED | Igual: la salida de `vault_arch` no está publicada con el SHA del candidato |
| QG-02 | BLOCKED | Exige `completo: true` de la auditoría del SHA y evidencia de la política con ese SHA |
| QG-03 | BLOCKED | La suite se ejecuta correctamente, pero el recibo JUnit del SHA del RC se emite en el mismo acto de cierre |
| QG-04 | BLOCKED | Seguridad parcial verificada; falta el artefacto de evidencia con el SHA |
| QG-05 | BLOCKED | Paridad CLI/MCP 5/5 local reportada en rondas previas, no regenerada para este SHA |
| QG-06 | BLOCKED | Wheel probada en Windows; la matriz multiplataforma depende de la CI |
| QG-07 | **BLOCKED** | `CI_PENDIENTE`: los runs siguen `queued` por bloqueo de cuenta (ver `CI-diagnostico.md`) |

**Lectura honesta:** el producto funciona y las puertas técnicas están verdes,
pero **no se declara QG-07** ni release. La diferencia entre "esto funciona" y
"esto está acreditado para terceros" es exactamente la que QA pidió no borrar.

## Bloqueos externos

1. **CI**: 25 jobs por run, todos `queued`, `runner_id: 0`, 12/12 runs sin
   completar, GitHub operativo, repo público, acciones habilitadas. El endpoint
   de facturación responde 404 al token: **requiere al propietario** (límite de
   gasto / método de pago / política de organización).
2. **Evidencia histórica** (OBS-R06-01/03): el auditor mide parches, no blobs;
   `forma_secreto: 0` no prueba ausencia universal. Documentado como límite.
3. **Reescritura de historia**: decisión exclusiva del propietario.

## Lo que NO se ha hecho

- No se fusionó PR #1 ni PR #2; `main` intacto (`1c34754` remoto).
- No se reescribió historia, no hubo `push --force` ni `reset --hard`.
- No se amplió ninguna baseline (la de arquitectura reubica 5 entradas, no crece).
- No se atribuyó PASS a ningún run en cola.
- TD-0003/Q04–Q07 y TD-0008 quedan **implementados**; no se declaran "certificados"
  por QA.
