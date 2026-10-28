# Archivo: `qa/review-arquitectura-trazabilidad-e8f7aea-20261025`

- Commit(s) sobre la rama de trabajo:
  - `9919c57e9ad8060eedfef5277e40d1e540df383d` 2026-10-25 — docs(qa): auditoria constitucion inventario 699 recursos y grafo 703 relaciones e8f7aea
- Base: `e8f7aea78be9368932b35a7aa74fa539c8b00774`
- Tag de conservación: `archivo/qa/review-arquitectura-trazabilidad-e8f7aea-20261025`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — Constitución y trazabilidad (R10, 2026-10-25)

**SHA de la capa examinado:** `e8f7aea78be9368932b35a7aa74fa539c8b00774`  
**Candidato de producto referido:** `31dfa462e87f5dcdb703e649e840e826a136ba50`  
**Rama del ejecutor:** `work/release-cli-mcp-20261025`  
**Rama exclusiva QA:** `qa/review-arquitectura-trazabilidad-e8f7aea-20261025`

**Alcance de esta revisión:** lectura estática directa en GitHub de Constitución 0.1, inventario, generador, grafo, tests, registro de veredictos, divergencias, mediciones, diagnósticos QG-02, documento AS-IS/TO-BE, PR #3 y GitHub Actions. **No se han ejecutado las pruebas locales, la wheel ni una verificación completa independiente de los 699 recursos.**

## Veredicto general

**ACEPTADO COMO AVANCE DOCUMENTAL / QA_REQUIRES_CHANGES PARA CERTIFICACIÓN.** Se reconoce la implementación de una capa aditiva y un primer inventario reproducible (699 recursos, 703 aristas, 10 divergencias y 15 hallazgos documentados según el generador). **La Constitución continúa DRAFT, sin ratificación; la cadena propósito → requisito → contrato → implementación → verificación → evidencia → QG → veredicto todavía NO existe de punta a punta.** No publicar release ni fusionar a `main`.

## Hallazgos que deben entrar a la siguiente ronda, por orden

**QA-ARC-01 — P1: grafo no implementa la trazabilidad prometida.** En `grafo-trazabilidad.json` hay 703 relaciones: PROVIDES 314, IMPLEMENTS 170, APPLIES_TO 82, OWNS 68, CONSUMES 64, VERIFIES 3 y AFFECTS 2. No existen `DERIVED_FROM`, `PRODUCES_EVIDENCE`, `DEPENDS_ON`, `RESOLVES`, `BLOCKS`, `APPROVED_BY` ni cadenas recurso→test→artifact→QG→veredicto, aunque la sección F de la Constitución afirma que el grafo las materializa. En `generar_inventario.py` se intenta `inv.arista(rid, cruce["from_context"], "DEPENDS_ON",...)`, pero `arista()` descarta silenciosamente los destinos que no sean IDs inventariados; por eso el grafo no tiene ninguna DEPENDS_ON. Las normas crean 82 auto-aristas `APPLIES_TO` de norma a sí misma, sin identificar el recurso sujeto. Enlace a tool/CLI/MCP no debe darse por comprobado si el destino no existe. **Remedio:** aristas con IDs de ambos extremos, error/registro de aristas sin resolver; contratos y IDs específicos para tests, evidencias, subchecks, decisiones, hallazgos y promesas; al menos cadenas E2E reales para QG-00, QG-02, QG-06 y un caso CLI↔MCP; pruebas negativas de relaciones faltantes, auto-aristas vacuas y cobertura de caminos. Medir cobertura por tipo, no inflar números.

**QA-ARC-02 — P1: "VERIFICADO" no significa funcionalmente aprobado.** En el generador se marca VERIFICADO al encontrar un fichero, su tamaño o una declaración del catálogo: 686/699 son verificaciones de **existencia/fuente**, no 686 verificaciones de comportamiento. Ejemplo: tool `vault_audit` indica "publicada en el catálogo" y tiene vacíos `related_tests`, `related_quality_gates`, `evidence`, `inputs` y `outputs`. **Remedio:** dividir `discovery_status` de `verification_status` y `acceptance_status`; no representar como certificación operacional el descubrimiento estructural. Conservar los 699 IDs y la cifra de fuente como medición histórica sin reclasificar artificialmente.

**QA-ARC-03 — P1: registro de veredictos no constituye un ledger de decisiones.** `registro-veredictos.yaml` contiene 56 entradas, **todas** con `estado_posterior: NO_DETERMINADO`, fecha en blanco, acción/cierre/prueba en blanco y rutas `origin/origin/qa/...` incorrectas. Repite dictámenes históricos porque recolecta encabezados repetidos del mismo buzón en múltiples ramas. **Remedio:** deduplicar por identidad del dictamen + SHA/commit de publicación y hallazgo, conservar la lista cruda como corpus, extraer decisión exacta respaldada (ACEPTADO / CON OBSERVACIONES / REQUIERE CAMBIOS / BLOQUEADO); corrección y cierre separados, sin atribuir aprobaciones no emitidas; corregir ref `origin/origin` y probar las referencias.

**QA-ARC-04 — P1: dos fichas de divergencia confunden identidad histórica y estado vigente.** En `divergencias-archify.yaml` los campos `sha_referencia_snapshot` y `sha_codigo_actual` están rellenados con el mismo SHA de generación `f049b1b`, aunque el snapshot corresponde a otra revisión. Además las fichas de cinco cruces todavía existentes consignan `es_deuda_viva:false`; una reubicación real del origen no extingue el cruce. **Remedio:** identificar procedencia Git real del snapshot o `NO_DETERMINADO`, registrar SHA vivo por separado, clasificar la deuda viva y distinguir 10 divergencias de inventario de 5 cruces de código. La propuesta A/B/C sigue pendiente del propietario. Prohibido cambiar baseline o marcar ratificado sin autorización.

**QA-ARC-05 — P1: QG-02 contiene un defecto de producto reproducido por el ejecutor.** En escenario B, un runtime limpio creado por el producto arroja **AP-39** por tres términos de vocabulario presentes sin entrada de bitácora (`INC-0015`). Esto no es una mera decisión del propietario ni se resuelve cambiando el alcance del gate. **Remedio:** reproducir con nuevo runtime descartable, atribuir el origen de los términos (bootstrap, vocabulario, ledger o migración), corregir causa sin relajar AP-39, probar normalización y trazabilidad de autoria y repetir E2E/26 puertas/suite. El escenario A conserva **14 hallazgos reales** en su sandbox de evidencia; clasificar/limpiar los 13 documentos bajo control del proyecto sin falsificar evidencia histórica; la entrada AP-36 de `vault-backups` externo NO se elimina sin inventario/consentimiento del dueño de datos.

**QA-ARC-06 — P1 saneamiento público de artefactos.** Los archivos publicados `diagnostico-escenario-a.json` y `hallazgos-qg02.yaml` conservan fragmentos identificables de una ruta local después del marcador de saneamiento, y la Constitución incluye un nombre de autor en comentario de cabecera. **Remedio:** ejecutar el verificador de saneamiento contra **todos** los documentos nuevos y sus logs; preservar como histórico sin exponer nuevos datos privados, no citar los valores en reportes. Si se decide eliminar información de commits ya públicos, pedir autorización específica de revisión de historia; no force-push.

**QA-ARC-07 — P2: deriva documental y trazabilidad de versión.** Los inventarios, diagnósticos y `mediciones.json` declaran `sha=f049b1b...` mientras HEAD es `e8f7aea...`; como el generador crea versiones antes del commit, deben distinguirse `source_sha`/`source_tree` de `artifact_commit_sha`, evitando referencia circular. En `ARQUITECTURA-ASIS-TOBE.md` se titula `Puertos (23)` pero hay **68 puertos**: 23 son pares de cruces. Hay referencias a `audits/architecture/arquitectura-asis-tobe.md` en minúsculas que no coinciden con el nombre real en mayúsculas; corregirlas y probarlas en FS sensible a mayúsculas.

**QA-ARC-08 — P2: fichas de hallazgos incompletas y pruebas débiles del corpus.** Las fichas INC-0001..15 tienen `impact: ""`, `resolution_options: []` y `evidence` que apunta a la propia ficha, no directamente al log del verificador, exit, SHA y hash. En tests, `test_el_inventario_esta_generado...` comprueba un nombre de generador, y `test_ninguna_relacion...` solo comprueba `detail` no vacío; no verifican verdad semántica. `test_la_lista_de_aceptaciones...` hace `pytest.skip` si una entrada aparece ratificada, precisamente cuando debería auditarla. **Remedio:** evidencia primaria y checks de integridad, pruebas semánticas negativas, legitimidad de ratificación y no-aceptación. Endurecer generación de IDs: `_id()` trunca SHA1 a cuatro dígitos hex y `alta()` silencia colisiones; detectar colisiones y aumentar longitud sin romper IDs ya publicados sin plan de migración.

## Estado de GOAL y decisiones reservadas

- Capa documental AS-IS/TO-BE y constitución 0.1: **implementadas como DRAFT, aún no aceptadas como norma**.
- Resultados locales reportados por ejecutor: 26/26 puertas tras corrección focalizada; última suite 6279 pass / 13 skip / 1 fail y reparación posterior focalizada; **suite completa del SHA `e8f7aea` no concluida**. No declarar 0 failed.
- CI para `e8f7aea`: run `40264878301` **queued**, sin conclusión; QG-07 BLOCKED, no afirmar causa administrativa concreta sin datos.
- DRAFT PR #3 no fusionado; `origin/main=1c34754258441550139ce895e182ab219c93f9bb` intacto.
- Decisiones del propietario: Constitución, alternativa A/B/C de cinco cruces, política QG-02 (sin eximir defectos del producto), destino de backups ajenos, historia publicada, acciones administrativas de CI.

## Orden de continuidad QA

Continuar en la rama del ejecutor desde `e8f7aea` sin tocar `main`. Primero proteger privacidad y corregir semántica del inventario/grafo/veredictos/SHAs; luego reparar AP-39 en runtime de prueba; después reconciliar evidencia de escenario A sin eliminar backups de terceros; ejecutar nuevas pruebas focalizadas, 26 puertas y suite completa del SHA final; generar y verificar recibos externos y devolver nuevo candidato QA con estados auténticos de QG. La Constitución no se ratifica automáticamente; no modificar decisiones A/B/C, QG-02 ni historia unilateralmente. Publicar el reporte del ejecutor con explicación de causas y vínculo por cada incidencia.

**Dictamen final de esta ronda: `QA_REQUIRES_CHANGES` para cierre del GOAL de arquitectura, `CONSTITUCION=DRAFT_RECOGNIZED`, `TRACEABILITY=PARTIAL`, `AP39=OPEN`, `QG-00..07=BLOCKED`.**

