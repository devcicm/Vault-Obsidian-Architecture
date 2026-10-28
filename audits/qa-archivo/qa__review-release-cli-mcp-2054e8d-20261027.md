# Archivo: `qa/review-release-cli-mcp-2054e8d-20261027`

- Commit(s) sobre la rama de trabajo:
  - `8be11d312b93bd468c4f21554833e0af163a6701` 2026-10-27 — docs(qa): revisar R17 verificacion decisiones y CI 25/25
- Base: `2054e8daa2a4d903c8d30bee84acba32a44e1780`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-2054e8d-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R17, producto 015b776 y HEAD 2054e8d (2026-10-27)

**Producto congelado:** `015b7765b80cac21c6dcf859ae075d036cd01def` (tree `d190fd243567556e824795154b6fd44bd76309d5`).  
**Fix de carrera R17:** `5970dfbbb835b0ae4958e2ee8384d343ea52fd27`.  
**HEAD documental del ejecutor:** `2054e8daa2a4d903c8d30bee84acba32a44e1780`.  
**Rama QA:** `qa/review-release-cli-mcp-2054e8d-20261027`.  
**Dictamen previo:** `7d2679a` para R16 sobre `09e849c`.

**Método:** revisión estática del repositorio y de diff `015b776→2054e8d`; inspección de `politica_certificacion_compuesta.py`, sus tests, manifiesto, decisiones, plan B, protocolo, PR y GitHub Actions; lectura del log del job fallido en `09e849c`. QA **no ejecutó localmente** suite, wheel, 27/27 E2E o tests del contrato propuesto.

## Veredicto

**R17: correcciones de CI y estructura de la propuesta RECONOCIDAS; implementación normativa y release NO APROBADOS.**

- CI del producto `015b776`: run `40442954197`, **25 jobs completed/success**, workflow completed/success — verificado directamente.
- CI fix R16 `55ad340`: run `40456389815`, **25/25 success** — verificado.
- CI delta `09e849c`: run `40464661392`, **24/25 success + 1 failure**; el log de Windows Python 3.10 contiene `shutil.Error` por desaparición de `vault-sandbox/00_System/.locks` durante `copytree`. No se falsifica su fallo.
- CI fix R17 `5970dfb`: run `40467869545`, **25/25 success** — verificado. En el código se centraliza `tests/sandbox_fixture.py::copiar_vault` y se incluyen regresiones; evidencia consistente con la causa.
- CI HEAD documental `2054e8d`: run `40472633327`, al último muestreo **in_progress, 13 jobs success y 12 en ejecución, sin conclusión**. No declarar éxito antes de conclusión.
- `main=1c34754258441550139ce895e182ab219c93f9bb` intacto. PR #3 OPEN/DRAFT, sin merge.
- `QG-00/QG-01`: BLOCKED por diez divergencias/deuda arquitectónica pendiente de DEC-02; `QG-02`: BLOCKED por residuo AP-36 y DEC-03/DEC-04; `QG-03..06`: PASS en recibos del ejecutor, aún subordinados a los prerrequisitos. `QG-07`: BLOCKED por puertas previas y falta de autorización, **NO por una CI de producto fallida**.
- `DEC-01..06` permanecen sin ratificación; `DEC-06` no corresponde hasta QG y QA favorables.

## QA-R17-QG02-01 (P1 ANTES de activar opción C): los metadatos de acto y custodia todavía son autoafirmaciones

La propuesta `audits/fase2/politica_certificacion_compuesta.py::_motivos_decision` corrige el error R16 de `decision_ref` texto libre y exige estructura `id/estado/firmante/fecha/referencia/alcance/custodia`. **Es una mejora real, pero no acredita que la ratificación provenga efectivamente del propietario.**

- `referencia` se verifica **solo** con regex de 40 caracteres hexadecimales; no se comprueba que el objeto Git exista, contenga el documento de aprobación, identifique el acto, ni que el propietario lo haya autorizado.
- `firmante` acepta **cualquier** string no vacío.
- `custodia.referencia` solo requiere string no vacío; `custodia.verificada: true` es un booleano suministrado por la misma entrada, no una verificación independiente de hash/acto.
- El caso positivo `test_el_positivo_usa_una_decision_formal_y_sintetica` usa SHAs `"d"*40`/`"e"*40`, un firmante ficticio y `verificada: true`, y exige **PASS**. El fixture sintético **es legítimo como prueba unitaria del parseo**, pero demuestra que la función actual verifica el formato, **no la autenticidad**. No tratar el PASS sintético como prueba de autoridad real.

**Remedio obligatorio antes de integrar con QG-02 de producción:** separar validación del esquema de **verificación de autoridad** y **custodia**. Resolver la referencia inmutable desde una fuente autorizada, confirmar existencia y contenido, que el acto mencione el residuo preciso, autoridad/identidad validada y estado actual RATIFICADO; cotejar también el acta de custodia con inventario/hash y propiedad. Ningún simple campo `RATIFICADO` o `verificada:true` de un recibo autoemitido concede autorización. Para controles ejecutados en un entorno sin fuente autorizada, **BLOCKED**. Añadir negativas: SHA hexadecimal inexistente, commit existente pero ajeno, firmante no autorizado, falsa custodia `verificada:true`, acto referido sin contenido o revocado, contenido no coincidente. **No inventar ni requerir criptografía que el proyecto no tenga**; usar una fuente de autoridad confiable definida por el propietario, con su identidad y procedencia.

**Importante:** DEC-03 sigue PENDIENTE y el módulo es una propuesta aislada; la presencia de este hallazgo **no implica que el producto distribuido haya adoptado una política insegura**. Impide considerar suficiente el ejecutable para certificar excepciones en el futuro.

## QA-R17-DOC-01 (P2): encabezado histórico incompatible con el contrato actual

El comentario inicial en `audits/fase2/CANDIDATO-RELEASE.yaml` aún dice `HEAD^ == product_sha` y que esa igualdad se comprueba en `tests/test_manifiesto_candidato.py`, pese a que el cuerpo del manifiesto y el test ahora usan **ascendencia**, no paternidad inmediata. Corregir el encabezado y la descripción inicial del test para describir el contrato vigente. Mantener el campo `doc_parent_sha` como **commit de publicación inicial**, no como padre actual. No modificar `product_sha` ni hashes para maquillar.

## Pendientes de propietario — decisiones separadas, sin automatizar

1. **DEC-02:** elegir opción B de migración compatible (si la ratifica) con subopciones **I2-a + COST-a** propuestas, latencia audit ≤5 s, deprecación una versión, I1–I5, descenso de cruces 5→3 y divergencias 10→0 sin inflar baseline ni sustituir el snapshot para esconder deuda. Después, implementación real y **nuevo SHA producto con revalidación completa**; alternativamente ratificar otra opción con riesgos expresos.
2. **DEC-03:** ratificar o rechazar QG-02 compuesto C **solo después de corregir la vinculación a una decisión verdadera**. Cambio de política/catalogo requiere autorización explícita, tests negativos y nueva QA.
3. **DEC-04:** backup externo histórico (66 ficheros, ~854 KB según ejecutor): lectura y tres hashes reportados; **sin mover/archivar/comprimir/purgar** sin autorización expresa del custodio. Elegir preservación/custodia/movimiento/purga con evidencia y rollback.
4. **DEC-01:** Constitución DRAFT. **DEC-05:** conservar historia o autorización explícita de saneamiento, sin force-push. **DEC-06:** autorización de release **posterior** a QA favorable y QG-00..07 efectivos.

## Secuencia recomendada

- El ejecutor puede **sin autorización extra**: corregir QA-R17-QG02-01 SOLO en la propuesta de contrato y sus tests, corregir comentarios DOC-01, verificar CI del HEAD y remitir las matrices de decisión; no tocar política de producción ni datos históricos.
- El propietario debe decidir DEC-02, DEC-03, DEC-04 y después DEC-01/05 según alcance; no suponer aprobación por preferencias o instrucciones informales de otro agente.
- Solo **tras autorización**: implementar el plan arquitectónico ratificado, cambiar catálogo/política si corresponde, manejar backup según acta, congelar SHA nuevo, repetir gates/suite/E2E/CI, QA independiente y autorización de publicación posterior.
- Si el GOAL sigue `BLOCKED_OWNER_DECISION` es una salida legítima y **no debe cerrarse ni disfrazarse de release autorizado**.

**Dictamen formal:** `R17-CI-FIX=ACCEPTED_SCOPED`, `QA-R16-QG02-01/02=SCHEMA_IMPROVED`, `AUTHENTICITY_OF_OWNER_ACT=NOT_VERIFIED`, `QG-00/01/02/07=BLOCKED`, `DEC_01..06=OWNER_PENDING`, `RELEASE=NOT_AUTHORIZED`, `GOAL=OPEN`. Se conserva la independencia QA y `main` sin modificación.

