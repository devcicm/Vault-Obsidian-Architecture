# Buzón QA → agente ejecutor — dictamen de ronda 1

**De:** QA arquitectónico (ChatGPT). **Para:** agente local. **Rama evaluada:** `audit/archify-governance-20261024`.
**SHA base:** `f3aaafc34a4ca719070a55f642452d52c107b58d`.
**SHA HEAD revisado:** `f6a53879a01b607c7aeb1f15f6406940a819936d`.
**Método:** revisión estática de commits, diff y archivos por GitHub; **QA NO ejecutó pruebas en su sandbox**. Las salidas de tests citadas a continuación son afirmaciones del ejecutor en mensajes de commit, todavía sin anexos de logs completos.

## Commits revisados (GitHub)

| Tarea | SHA | Cambio observado | Decisión QA |
|---|---|---|---|
| Q00 | `acb20da` | Bitácora de línea base: Python 3.14.3, rama limpia al inicio, guard 37 cruces / 8 fuera de puerto, AP-39 3/3 reportadas. | **ACEPTADA como evidencia documental de baseline** (no implica aprobar suite completa). |
| Q01 | `4fededd` | Publica los puertos `resolucion_de_vocabulario` y `registro_de_nuevos_terminos` de Índices; quita A/B de baseline: 8→6. No cambia funciones de escritura. | **CONFORMIDAD ESTÁTICA; aceptación final condicionada** a reporte actual del guard y regresión. |
| Q02 | `ec5e56e` | Tres pruebas E2E añadidas a `test_ap39_contrato.py`: fracaso de escritura, éxito con deduplicación, fallo del ledger; 6/6 reportadas en unittest y pytest. | **AJUSTES SOLICITADOS**: completar afirmación sobre fallo observable y evidencias. |
| Q03 | `f6a5387` | Publica `enumeracion_indexable` → `vault_reindex:notas_indexables`; agrega tres tests de raíces/filtros/equivalencia; baseline 6→5. | **CONFORMIDAD ESTÁTICA; aceptación final condicionada** a logs, guard y gates. |

**Resultado confirmado de GitHub:** desde `f3aaafc` hay 4 commits, con cambios en 8 archivos; `main` no es destino de estos commits. La baseline `scripts/arch-baseline.json` ahora enumera 5 cruces fuera de puerto (D–H). La ausencia de esos tres cruces en esa lista debe conciliarse con la salida real de `vault_arch.py --check --strict`.

## Observaciones de QA

1. **Evidencia de ronda no entregada en buzón.** `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` sigue en plantilla `PENDIENTE DE RESPUESTA`, a pesar de los 4 commits y del log parcial Q00. Actualízala con matriz por Q00–Q03, SHA base/final, comandos, salidas o rutas de logs, cambios y riesgos. La ausencia del buzón no invalida los commits, pero impide cerrar formalmente el ciclo de handoff.
2. **Q02 – falta aserción del error observable.** `test_fallo_del_ledger_no_tumba_la_nota` comprueba `ok`, existencia de nota y ausencia de archivo ledger, **pero no comprueba** `sobre.get("vocabulary_recorded") == -1`. El código `scripts/vault_write.py` expone `vocabulary_recorded` (no `recorded`, usado por `registrar_tags_de_nota`). Corregir docstring/afirmación y añadir la aserción, manteniendo prueba de nota persistida; evitar falso verde donde el fallo se silencia.
3. **Q01/Q03 – diffs de contratos compatibles con el inventario.** `vault_tags.apply_vocabulary` es consulta previa a persistencia; `vault_tags.record_new_tags` registra después. `vault_reindex.notas_indexables(root=...)` delega a `notas_en_disco` del dominio. Declararlos como puertos en `vault_arch.py` es una corrección plausible del contrato de superficie, no una refactorización funcional. Los tests de Q03 ejercen raíz alternativa y filtros; no se presume validación de todas las rutas consumidoras.
4. **Integridad pendiente.** El HEAD registra una ejecución de GitHub Actions «Vault CI» en estado `queued` sin conclusión al momento de esta revisión; tampoco hay logs de suite integral ni de las 26 puertas adjuntos al buzón. No anunciar `PASÓ` global.
5. **No normalizar deuda artificialmente.** La baseline bajó 8→5 y no creció: favorable. Comprobar que el guard real cuenta 5 y no oculta cruces nuevos; no editar baseline para esconder un fallo.

## Respuesta solicitada al ejecutor — ronda 1B

- Ajustar Q02 con `assertEqual(sobre.get("vocabulary_recorded"), -1)` y aclarar el nombre del campo en la explicación.
- Ejecutar y documentar en HEAD actualizado: `python -m unittest discover -s tests -p "test_ap39_contrato.py"`, `python -m unittest discover -s tests -p "test_puerto_notas_indexables.py"`, `python scripts/vault_arch.py --check --strict` y `python scripts/vault_gate.py --strict`. Adjuntar `exit code`, resumen/salida, Python, SO, SHA.
- Informar del resultado de CI y, si no hubo suite completa, marcarla PENDIENTE con causa. No sustituir evidencias con número de pruebas escrito en `AGENTS.md`.
- Actualizar exclusivamente el buzón del ejecutor y logs propios; **no sobrescribir este buzón QA** ni hacer merge a `main`. Enviar SHA del siguiente commit y dudas para asignar Q04–Q07.
- Conservar el enfoque ODD: cambio mínimo, causa, invariantes y comprobaciones empíricas.

**Dictamen global:** **EN REVISIÓN QA / REQUIERE EVIDENCIA Y AJUSTE DE Q02**. Aceptación documental de Q00, conformidad estática Q01/Q03 y Q02 parcialmente verificada por código, pero **ninguna validación empírica ejecutada por QA**. Quality Gates de cierre (Q12) siguen diferidos.

---

# Dictamen QA — cierre técnico local de ronda 1B (2026-10-25)

**Emisor:** QA arquitectónico (ChatGPT). **Destinatario:** ejecutor local.  
**Rama:** `audit/archify-governance-20261024`.  
**SHA ejecutor evaluado:** `3913baa18122d71596060ce93eeec58532f91184`; código corregido AP-37 en `f24a9b82913294dd3295058a5b56361cc2af229f`.  
**Base de comparación de esta etapa:** `bcc1f8b69a2f8d7d0e0f20bf5d2f86c9895e1a75`.  
**Método:** verificación remota de historial, cambios de código, informe y logs de GitHub. **QA no ejecutó de forma independiente la suite ni las puertas de calidad.**

## Verificación y dictamen por hallazgo

| Hallazgo | Evidencia revisada | Dictamen |
|---|---|---|
| H-QA-01 AP-37 | Diff de `scripts/vault_noop_audit.py` (+8 líneas): declara `vault_frontmatter_completar: {"07_Knowledge/x.md": "nota"}` en `FICHEROS_DEL_EJEMPLO`; logs antes (exit 1, NOTE_NOT_FOUND) / después (exit 0, herramienta medida con escritura real) | **ACEPTADO para el alcance local**. No se relajó la detección AP-37. |
| H-QA-02 doc_staleness / gobernanza | `R1B-CIERRE-gates.txt`: `gates_total=26`, `passing=26`, `failing=0`, exit 0 reportado; `R1B-CIERRE-entorno.md` documenta bootstrap canónico | **ACEPTADO como resultado local documentado**. |
| H-QA-03 suite integral | `R1B-CIERRE-suite.txt`: pytest sobre Windows/Python 3.14.3, 6,141 passed, 11 skipped, 2 warnings, 0 failed, 1019.94 s; exit 0 consignado por ejecutor | **ACEPTADO como resultado local documentado**, no como certificación multiplataforma. |
| H-QA-04 arquitectura | `R1B-CIERRE-arch.txt`: `ok=true`, `broken_ports=[]`, `new_off_port_crossings=[]`, `off_port_total=5`, `off_port_baseline=5` | **ACEPTADO** para invariantes definidos en esta ronda. Permanecen cinco cruces conocidos D–H como deuda posterior. |
| H-QA-05 CI | Estado GitHub Actions del SHA `3913baa`: workflow `40168207630` en `queued`, sin conclusión al comprobar; runs anteriores también en cola | **PENDIENTE**. No declarar CI aprobada ni producto publicable. |

## Decisión QA

**ACEPTADO CON OBSERVACIONES: cierre técnico LOCAL de ronda 1B.**

Esta decisión **no equivale a** autorizar merge a `main`, declarar la distribución lista, emitir un release estable, certificar compatibilidad Linux/macOS ni afirmar paridad CLI–MCP. No requiere una nueva ronda 1B por los hallazgos locales ya cerrados a menos que aparezca nueva evidencia contradictoria.

**Observaciones de alcance y verificación:**

1. Los resultados de pruebas y gates son verificables documentalmente en GitHub, pero fueron ejecutados por el agente local. QA no los reprodujo en un entorno propio.
2. `R1B-CIERRE-entorno.md` documenta tres intentos fallidos antes del cuarto exitoso; esta trazabilidad se conserva y no invalida la última corrida.
3. Las pruebas se ejecutaron sobre el SHA de código `f24a9b8`; commits posteriores agregan evidencias/informe, no modifican código según el diff revisado. El SHA del HEAD ejecutor es `3913baa`.
4. Las 11 omisiones y dos warnings deben mantenerse visibles; no equivalen a fallos de suite en el alcance informado.
5. La cobertura de otras versiones de Python y plataformas, integración CI y criterios de empaquetado/distribución quedan pendientes para la fase posterior.
6. Los cinco cruces fuera de puerto conocidos D–H permanecen como deuda vigilada, no como nuevas regresiones.

## Comunicación y siguiente ronda

- **QA** conserva la propiedad editorial de `audits/handoff/RESPUESTA-QA.md`.
- **Ejecutor** conserva la propiedad de `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` y sus logs.
- **Propietario** decide autorización de la próxima ronda, cambios en `main`, lanzamiento y prioridad entre deuda arquitectónica (Q04–Q07) y preparación para distribución.
- **No iniciar Q04–Q07 automáticamente** ni hacer merge de PR #1 a `main`.
- Una vez disponible CI para el SHA de la rama, verificar estado, matriz multiplataforma, dependencias de wheel (incluido PyYAML) y pruebas JSON-RPC; registrar evidencia antes de solicitar autorización de distribución.
- Para producto CLI + MCP, programar en fase independiente una validación de instalación limpia, operaciones E2E reales y paridad de contratos/adaptadores.

**Estado:** RONDA 1B CERRADA EN ALCANCE LOCAL; CI Y RELEASE PENDIENTES.

