# Archivo: `qa/review-release-cli-mcp-5836474-20261025`

- Commit(s) sobre la rama de trabajo:
  - `fabe442765ca5bdf5c9ab68201058a34e716b2e3` 2026-10-25 — docs(qa): dictamen SHA 5836474, bloqueos QG y harness R07
- Base: `5836474afc8006e1846eb08b1ff1b12fbc208626`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-5836474-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — Entrega R07 (SHA 5836474, 2026-10-25)

**SHA examinado:** `5836474afc8006e1846eb08b1ff1b12fbc208626`.  
**Rama ejecutor:** `work/release-cli-mcp-20261025`.  
**Rama QA independiente:** `qa/review-release-cli-mcp-5836474-20261025`.  
**Antecedente obligatorio:** `1e75d94d007dfe5eeee03e999348d3410c11e18b` (QA del SHA `4c66fc2`).  
**Alcance verificado:** diff GitHub 4c66fc2→5836474, script `audits/fase2/recorrido_terceros_r07.py`, colector QG, tests, catálogo QG, PR #3 y runs de Actions. **QA no ejecutó wheel, suite, harness ni puertas localmente.**

## Dictamen

**GOAL EN PROGRESO; NO `READY_FOR_QA_WITH_EXTERNAL_BLOCKER` TODAVÍA.** Coexisten bloqueos externos de CI y pendientes técnicos internos. **NO aprobado para merge a `main` o release.**

**Estado constatado:**

- `main` sigue en `1c34754258441550139ce895e182ab219c93f9bb`.
- PR #3 sigue `OPEN/DRAFT`, apunta a `main`, sin merge, SHA actual `5836474`.
- El commit `5836474` **solo** añade el harness R07 y `from __future__ import annotations` al test `tests/test_colector_qg.py`. **NO contiene modificaciones a `colector_qg.py`** y, por tanto, las brechas QA-RC-02d/e/f del dictamen previo permanecen pendientes.
- El agente **reportó** 6272 passed/13 skipped/**1 failed** en la corrida anterior a `5836474`, debido a una anotación PEP 604, y 40 pruebas focalizadas en verde tras corregirla. **No existe reporte concluyente de suite completa sobre `5836474`**.
- El agente **reportó** 26/26 puertas para código anterior al SHA y un recorrido parcial de 15–16/19; no hay evidencia suficiente del conjunto final para acreditar gates.
- Run `40242263586` del SHA `5836474`: 25/25 jobs `queued`, ninguno `completed` al consultar. `QG-07=BLOCKED`. La causa administrativa precisa NO está demostrada.

## Hallazgos vigentes

**QA-RC-02d (P1): el colector aún permite CI sin matriz verificada.** `estado_ci(..., jobs=None)` omite toda verificación de jobs y puede devolver `success`; `colectar(..., jobs_ci=None)` y la CLI `--jobs-ci` opcional conservan esa vía. Se tolera `conclusion=None` entre jobs, se compara por prefijo `startswith()` y los jobs suministrados no se asocian inequívocamente al run seleccionado. **Exigir obtención real de jobs del mismo run, run/status/conclusion/identidad verificables, match exacto y matriz completa; si no hay jobs o permisos, `BLOCKED`.** Negativas: jobs ausentes/null/queued, de otro run, prefijos engañosos, duplicados y jobs parciales.

**QA-RC-02e (P1): recibo individual no satisface todos los subchecks del catálogo.** `GATE_VERIFICADORES` registra un solo comando por QG, cuando `catalogo-qg.yaml` exige subcomprobaciones múltiples. `leer_recibo` admite un JSON `{"ok":true}` con hash coherente y los campos declarados como evidencia satisfactoria para una puerta, sin comprobar contenido específico del gate ni ejecución real. **Implementar motor/composición de checks obligatorios y derivar PASS de resultados efectivamente observados, no de un único JSON autocertificado.** QG-00 identidad+saneamiento+reconciliador; QG-02 26 puertas+auditoría completa; QG-03 suite+gates+E2E; QG-04 seguridad y dependencias; QG-05 paridad+AP-40; QG-06 artefacto+instalación limpia. Añadir negativos por subcheck faltante, artefacto genérico, resultado incompleto.

**QA-RC-02f (P1/operatividad): falta un productor reproducible de recibos verídicos.** La CLI del colector solo consume `--recibos`; no invoca los verificadores del catálogo para generar los recibos. Un script que escriba `PASS/exit=0` sin ejecución auténtica no sirve. **Agregar ejecutor de verificaciones controlado o ligar a un pipeline que ya ejecute y conserve las salidas, capturando exit, SHA, run, hashes y estado**, fuera del árbol del candidato.

**QA-RC-05a (P2): harness ahora publicado, pero no terminado.** `audits/fase2/recorrido_terceros_r07.py` existe por primera vez en el SHA `5836474`; el commit hace reproducible el **código del intento**, no garantiza resultado 19/19:
- Usa `os.environ["TEMP"]` y rutas `Scripts/python.exe`, `vault.exe`, `Lib/site-packages`: está limitado a Windows sin declararlo ni ofrecer alternativa multiplataforma; no confundir con prueba CI.
- El conteo exige exactamente **una** cuarentena, aunque existan restos previos; necesita identificar la cuarentena concreta creada en el run.
- Hash de contenido esperado calcula `contenido+"\\n"`, pero la herramienta normaliza el contenido; determinar bytes/hashes del archivo realmente persistido antes y después de clean/restore.
- El cliente MCP escribe `initialize`, `tools/list`, `tools/call` en una sola entrada, **sin `notifications/initialized` ni intercambio secuencial real**. Añadir cliente con espera, respuestas correlacionadas y deadline, usando el protocolo correctamente.
- `restore manual` usa `copytree(..., dirs_exist_ok=True)` hacia un vault nuevo, sin verificar igualdad completa del inventario restaurado ni ausencia de archivos extra. Validar bytes/hash y contenido sin mezcla de estados.
- `clean --dry-run` permite una mera aparición del texto `dry_run`, aun si la salida no confirma `dry_run: true`; estructurar el criterio de aceptación.
- El script elimina directorios fijos `TEMP/opencode/r07-venv`, `r07-consumidor/mi-vault`, `dist/rc`. **Usar un área descartable propia por ejecución con validación de propiedad y protección de paths**, no borrar ubicaciones posiblemente ajenas. El objetivo debe seguir siendo prueba segura, no daño a datos preexistentes.
- Confirmar que la wheel corresponde al SHA ensayado y reportar identificador, hash e integridad de cada paso. Si un paso falla, no atribuir PASS al conjunto.

**QA-RC-03 (decisión arquitectónica pendiente):** cinco cruces fuera de puerto aún registrados. La propuesta de excepción `permanente` exige ratificación **explícita** del propietario. Preferir eliminación real mediante composición legítima; ninguna exención se presume. Documentar impacto de A/B/C y mantener QG-01 bajo política real.

**Resultados finales pendientes:** suite completa 0 failed en el SHA final, 26 puertas del SHA, 19/19 E2E o justificación precisa de casos N/A, recibos externos verdaderos y producto instalado asociado al SHA. No reutilizar resultados de commits anteriores.

## Instrucción al ejecutor

**Continuar R08/R07 sin reiniciar el GOAL**: (1) obtener el resultado de la corrida completa, corregir/repetir si es incompleta; (2) reparar QA-RC-02d/e/f con pruebas negativas; (3) corregir/pulir harness y registrar 19/19 sobre wheel ensayada; (4) arquitecturar alternativa real de eliminación para los 5 cruces o dejar decisión del propietario expresamente pendiente; (5) publicar nuevo SHA, congelar, generar recibos fuera de árbol y acreditar QG-00..06; (6) mantener QG-07 bloqueado hasta CI concluida y evaluada. No editar este buzón de QA ni fusionar ramas.

**Estado formal:** `QA_REQUIRES_CHANGES`; `QA-RC-01f=ACCEPTED_SCOPED`; `QA-RC-02d/e/f=OPEN`; `QA-RC-03=OWNER_DECISION_PENDING`; `QA-RC-05=INCOMPLETE`; `QG-07=BLOCKED`; `MAIN_UNCHANGED`.

