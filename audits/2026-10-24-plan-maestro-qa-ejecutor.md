# Plan maestro QA ↔ agente ejecutor — 2026-10-24

**Rama:** `audit/archify-governance-20261024`. **Propósito:** cola ordenada de trabajo para revisión estática por QA y ejecución local por otro agente. **No es una certificación de pruebas.** Fuente: `audits/2026-10-24-bitacora-auditoria-y-handoff.md` y revisión del código en esta rama. El ZIP Archify corresponde a un snapshot anterior; revalidar todo contra el SHA ejecutado.

## Contrato de colaboración
- **QA:** aporta hallazgo, ubicación, evidencia, mecanismo causal, contrato/invariantes, propuesta, casos de prueba, criterios de aceptación. No marca PASÓ sin log.
- **Ejecutor local:** usa worktree/rama auxiliar por tarea; ejecuta pruebas antes y después, hace cambios mínimos, captura comando, salida, entorno, SHA y diff; devuelve commit/PR y posibles refutaciones.
- **QA:** revisa diff y evidencia, acepta/rechaza/solicita ajustes; actualiza este plan. No mezclar ni empujar sobre archivos que el ejecutor edita simultáneamente.
- **Estados:** PENDIENTE → EN ANÁLISIS → LISTO PARA EJECUTOR → EN EJECUCIÓN → EN REVISIÓN QA → ACEPTADO / RECHAZADO / BLOQUEADO. La lectura estática no equivale a ACEPTADO.
- **Regla de evidencia:** toda afirmación de prueba requiere comando + resultado + SHA + entorno. Un fallo o discrepancia se registra, no se oculta ampliando baselines.

## Cola priorizada (QA prepara → agente ejecuta → QA verifica)

| ID | Prioridad | Tarea y evidencia | Resultado esperado / aceptación | Estado |
|---|---|---|---|---|
| Q00 | P0 | Establecer baseline: `git status`, SHA, versión Python, tests existentes, CLI de arquitectura y normas; no alterar main. | Informe de línea base, comandos y logs; separar fallos preexistentes. | LISTO PARA EJECUTOR |
| Q01 | P0 | AP-39, A/B: `vault_write.py:1046,1394`; `vault_tags.py:307-372`; `vault_arch.py:405-420`. Revisar si exponer `apply_vocabulary` y `record_new_tags` como puertos explícitos o introducir contratos puros/efecto separados. | La resolución ocurre antes de guardar, el ledger solo después; fallo de escritura no añade tags; fallo de ledger no deshace nota; compatibilidad con otros escritores. | LISTO PARA EJECUTOR |
| Q02 | P0 | Ejecutar `python -m unittest discover -s tests -p 'test_ap39_contrato.py'` y agregar casos de escritura fallida, éxito, ledger fallido y duplicados. | Evidencia por caso y sin regresiones; corregir tests si están defectuosos, sin falsear aprobación. | LISTO PARA EJECUTOR |
| Q03 | P1 | C: `vault/ciclo_de_vida/sanacion.py:188-203` llama `vault_reindex.notas_indexables`; `scripts/vault_sanacion.py` es alias. Comparar puertos existentes en `vault_arch.py`. | Puerto de enumeración formal o interfaz equivalente, misma cobertura y semántica de raíz; sin cambiar `index_coherence` ya publicado. | LISTO PARA EJECUTOR |
| Q04 | P1 | D: `vault_norms_engine.py:136-152` usa `vault_mcp_catalog.check_params` fuera de puerto. Inspeccionar contrato de `check_contracts` antes de elegir. | Control AP-40 preservado; errores de catálogo observables; sin falso positivo de auditoría limpia. | PENDIENTE |
| Q05 | P1 | E/F/G: `vault_norms_engine.py:154-180` consume `vault_smoke.SIN_SMOKE`, `invocation`, `load_baseline` y `TOOLS_CATALOG`. | API de consulta estable o puertos explícitos; baseline inválida y falta de ejemplo reportadas; no silenciar error de control. | PENDIENTE |
| Q06 | P1 | H: `vault_norms_engine.py:182-197` usa `vault_voice.coverage()` fuera de puerto. | Contrato de cobertura publicado o adaptado; AP-43 distingue norma silenciosa de control no ejecutado. | PENDIENTE |
| Q07 | P1 | Riesgo transversal: `except (ImportError, OSError, ValueError): pass` en AP-40/42/43. Inspeccionar consumidores de `vault_norms_audit` y esquema de salida. | Señal explícita de control ejecutado/degradado/fallido; compatibilidad preservada; tests con excepciones inyectadas. | PENDIENTE |
| Q08 | P2 | Cruce Kernel→Autoría: `vault_errors.py` importa `vault.autoria.voz.speak`; `vault_arch.py` declara cruce permanente. | Decisión ADR: justificación o inversión de dependencia; fallo de voz no impide registrar error; test de degradación. | PENDIENTE |
| Q09 | P2 | Revisión de generación: `vault_servicio.py` y `docs/GOBIERNO.md` cambiados en rama. | Regeneración reproducible, diff estable, sin edición manual de derivados. | PENDIENTE |
| Q10 | P2 | Reejecutar reporte Archify sobre SHA actual y clasificar A–H como vigente, resuelto, justificado o falso positivo. | Cero cruces no justificados o deuda documentada con propietario; no alterar baseline para ocultar. | PENDIENTE |
| Q11 | P2 | Contratos y regresión integral: comandos de tests, CLI, packaging, errores de importación y documentación. | Logs de CI/local, matriz de aceptación y riesgos residuales. | PENDIENTE |
| Q12 | P3 | **Solo al cierre:** inventario de Quality Gates (arquitectura, contratos, integridad, seguridad, sanidad, regresión). | Propuesta de puertas, responsables, evidencias, política de bloqueo; evitar duplicados. | DIFERIDO |

## Primera entrega al agente local (Q00–Q03)
1. Confirmar rama, SHA, estado limpio y divergencias con main. Trabajar en worktree o rama derivada; no fusionar.
2. Ejecutar tests AP-39 tal como están, reportar salida exacta y errores de entorno.
3. Leer los dos caminos de tags; proponer diff mínimo **sin** adelantar el efecto del ledger. Añadir pruebas de fallo.
4. Comparar enumeración `notas_indexables` con otros puertos; proponer contrato con casos de raíz alternativa y exclusiones.
5. Devolver tabla `ID | SHA base | archivos | diff/commit | comandos | resultado | riesgo | dudas`. QA evaluará antes de aceptar.

## Registro de rondas
| Ronda | Responsable | Entradas | Salida y evidencia | Decisión |
|---|---|---|---|---|
| 0 | QA | Archify + GitHub + bitácora | Plan de Q00–Q12, análisis estático, sin tests ejecutados | Q00–Q03 listos para ejecución externa |

**No modificar `main` ni afirmar validación empírica desde este sandbox.** 
