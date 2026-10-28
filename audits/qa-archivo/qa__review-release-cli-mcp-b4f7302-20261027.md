# Archivo: `qa/review-release-cli-mcp-b4f7302-20261027`

- Commit(s) sobre la rama de trabajo:
  - `2369be8199d60411edbc2740986a8ffad274b9b7` 2026-10-27 — docs(qa): revisión R18 de autoridad y custodia antes de DEC-03
- Base: `b4f7302632281c56d9f86942fbe0b81ca619ee77`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-b4f7302-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R18, propuestas de autoridad DEC-03 (2026-10-27)

**SHA revisado:** `b4f7302632281c56d9f86942fbe0b81ca619ee77`.  
**Producto congelado:** `015b7765b80cac21c6dcf859ae075d036cd01def` (árbol `d190fd24…`).  
**Rama exclusiva QA:** `qa/review-release-cli-mcp-b4f7302-20261027`.  
**Antecedente:** dictamen QA-R17 `8be11d312b93bd468c4f21554833e0af163a6701`.  
**Método:** inspección estática de código, tests, expedientes DEC, manifiesto, rama, PR y jobs de CI por GitHub. **QA no ejecutó suite/E2E ni los tests focalizados.**

## Veredicto: AVANCE RECONOCIDO; CERTIFICACIÓN DE AUTORIDAD AÚN INCOMPLETA

- **Producto `015b776`:** CI `40442954197` comprobada, 25 jobs `completed/success`; el reporte del ejecutor aporta suite 6334/13/0, 26/26 y E2E 27/27. No sustituir sus artefactos de R14 por CI de otro SHA.
- **R18:** hay mejoras genuinas: el evaluador pasa a requerir `verificador_actos` real (sin él BLOCKED), comprueba objetos Git existentes, canal, contenido, distinción entre acto y custodia, y el manifiesto corrige ascendencia respecto del HEAD documental. Las 44 pruebas son **afirmación del ejecutor y revisión de fuente**, no ejecución QA.
- **QG-00/01 BLOCKED** por DEC-02; **QG-02 BLOCKED** por DEC-03/04; **QG-03..06 PASS** según recibos históricos del SHA producto; **QG-07 BLOCKED** por prerrequisitos, no por falta de CI del producto. `main=1c34754258441550139ce895e182ab219c93f9bb`; PR #3 OPEN/DRAFT, no fusionado.
- El registro `autoridades-de-decision.yaml` se autodeclara `PROPUESTA`; ninguna decisión de propietario se infiere por la existencia de código, un recibo o un commit escrito por el ejecutor.

## Hallazgos focalizados R18, en propuesta, antes de ratificar y conectar a producción

**QA-R18-AUTH-01 — P1: registro expresamente PROPUESTA puede actuar como fuente efectiva en el código.**
`cargar_registro()` normaliza la lista de autoridades y `verificador_desde_registro()` comprueba solo que exista el mapa; **no consulta `registro.estado` ni una ratificación independiente del registro/canal**. `tests/test_verificador_actos.py::test_el_registro_de_la_propuesta_es_una_propuesta_sin_autoridades_efectivas` incluso espera que `verificador_desde_registro(ROOT, datos)` produzca un objeto para la propuesta. Con commits que cumplen coincidencias de texto, podría aprobar cuando la configuración todavía declara `PROPUESTA`. **Antes de activar DEC-03:** una configuración DRAFT/PROPUESTA/no ratificada debe impedir un PASS de certificación, tanto desde la factoría como desde el evaluador; pruebas negativas contra commits verdaderos en repo descartable. La mera presencia de `autoridades` no constituye la puesta en vigor.

**QA-R18-AUTH-02 — P1: la identidad efectiva `autoridad` puede diferir del `firmante` que valida el esquema.**
`_motivos_decision()` exige `firmante` no vacío; `VerificadorActosGit._autoridad_de()` prefiere `decision.autoridad` cuando existe, sin exigir igualdad con `firmante`. Por tanto una decisión podría traer `firmante: cualquier-texto` y `autoridad: propietario-datos` y verificar frente a canales de propietario-datos, aunque el firmante declarado no esté registrado. **Antes de activar:** establecer un identificador canónico de autoridad, exigir correspondencia unívoca de todos los aliases y rechazar discrepancias; prueba negativa de `firmante` ajeno + `autoridad` registrado.

**QA-R18-AUTH-03 — P1/P2: el texto del commit no acredita inequívocamente la intención de RATIFICAR.**
`verificar_acto()` únicamente comprueba que el mensaje contenga el ID de decisión y tokens del residuo; rechaza ciertas palabras de revocación, pero no exige una declaración estructurada y positiva de aprobación. Un commit que **describe o propone** DEC-04, AP-36, ruta y huella sin ratificarlos puede pasar si otro registro autoafirma `estado: RATIFICADO`. **Antes de activar:** validar un acta formal con acción y estado explícitos (`RATIFICAR`, actor, ámbito, residuo, huella, canal, fecha) contra contenido inmovilizado, diferenciando `PROPUESTA`/`CONSULTA`/`RATIFICADO`/`REVOCADO`, y fallar ante ambigüedad. Prueba negativa sobre commit consultivo real que menciona todos los tokens.

**QA-R18-AUTH-04 — P2: custodia tiene menor vinculación semántica que el acto de decisión.**
`verificar_custodia()` comprueba commit distinto, canal, ID si viene y huella; no exige explícitamente que identifique la norma/ruta/ID del residuo y custodio aprobado, ni verifica la identidad Git declarada de ese segundo autor. El expediente DEC-04 exige custodia con autoridad y destino identificados. Establecer contrato de acta de custodia con ID obligatorio, autoridad/custodio permitido, ruta, norma, huella, alcance y operaciones permitidas; prueba negativa de custodio no autorizado.

Los defectos AUTH-01..04 afectan a un mecanismo **PROPUESTO y no conectado a QG de producción**. No se atribuyen como fallos del producto congelado; son condiciones para ratificar e implantar DEC-03 de forma segura. Tampoco debe presentarse Git/identidad compartida como firma criptográfica; el control de canal sigue siendo administrativo y requiere garantía del propietario.

## Secuencia autorizable, sin presumir firmas

1. Solicitar al propietario DEC-02: **preferencia técnica B + I2-a + COST-a** (si acepta ampliación de superficie en wheel), presupuesto <=5 s/audit, compat una versión, I1–I5, prueba de equivalencia, criterio 5→3 cruces y 10→0 divergencias y rollback. Hasta acto explícito, nada se implementa como opción elegida.
2. DEC-03: preferencia técnica C, pero corregir AUTH-01..04 **antes de ponerla en vigor**. Propietario define canal protegido y autoridad; un mero commit del ejecutor no certifica aprobación.
3. DEC-04: **NO purga** por implicación. Se puede recomendar designación de custodio y archivo de preservación no destructivo, pero ambas operaciones deben tener acto del propietario conforme al expediente. Conservar 66 ficheros y hashes mientras no exista autorización.
4. DEC-01 Constitución DRAFT y DEC-05 historia son decisiones separadas; DEC-06 release únicamente después de QA y todos los QG efectivos.
5. Una vez autorizadas y aplicadas las decisiones, producir **nuevo SHA de producto**; suite, 26 puertas, E2E desde wheel nueva, CI 25/25 de ese SHA, recibos QG y dictamen independiente; no reusar el `015b776` para código nuevo.

## Dictamen formal

`QA_R18=ACCEPTED_AS_DESIGN_PROGRESS`; `QA-R18-AUTH-01/02/03=P1_OPEN_PRE_ACTIVATION`; `QA-R18-AUTH-04=P2_OPEN_PRE_ACTIVATION`; `QG00/01=BLOCKED_DEC02`; `QG02=BLOCKED_DEC03_DEC04`; `QG07=BLOCKED_PREREQUISITES`; `RELEASE_NOT_AUTHORIZED`. Sin merge, tag, release, cambios a main, snapshot/baseline ni manipulación de datos externos.

