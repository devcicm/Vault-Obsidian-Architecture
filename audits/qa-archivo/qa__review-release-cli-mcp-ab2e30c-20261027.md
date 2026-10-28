# Archivo: `qa/review-release-cli-mcp-ab2e30c-20261027`

- Commit(s) sobre la rama de trabajo:
  - `222094f666b154fa068a7cf58f785c9cb31628ad` 2026-10-27 — docs(qa): dictamen R19 autoridad custodio acta vigencia y revocacion
- Base: `ab2e30c4cfb929e95c3c8ee4403aa640abfa8ac3`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-ab2e30c-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R19: autoridad/ratificación (2026-10-27)

**SHA del ejecutor inspeccionado:** `ab2e30c4cfb929e95c3c8ee4403aa640abfa8ac3`  
**Commit R19 de implementación:** `515f19646730e459a09f8fe45dbfd95946283b25`  
**SHA de producto congelado declarado:** `015b7765b80cac21c6dcf859ae075d036cd01def`, tree `d190fd243567556e824795154b6fd44bd76309d5`  
**Rama QA aislada:** `qa/review-release-cli-mcp-ab2e30c-20261027`  
**Dictamen precedente:** `2369be8` (R18; AUTH-01..04, según informe ejecutor).  
**Método:** inspección independiente del código versionado, diff 515f196→ab2e30c, registro de autoridades, pruebas, documentos de decisiones y workflow GitHub Actions. **No se ejecutaron localmente las 57 pruebas ni la suite del producto; verdes reportados por ejecutor y CI se distinguen de ejecución QA.**

## Estado verificado de Git y CI

- `main=1c34754258441550139ce895e182ab219c93f9bb` sin cambios. PR #3 `OPEN/DRAFT`, `merged=false`.
- `work/release-cli-mcp-20261025` en `ab2e30c`. La diferencia `515f196 → ab2e30c` es documental/manifest (informe de readiness, candidato release, buzón ejecutor).
- Run `40488879515` en `515f196`: `completed/success`. Run `40494674454` en `ab2e30c`: `in_progress`, conclusión pendiente al consultar.
- `audits/fase2/autoridades-de-decision.yaml`: **`estado: PROPUESTA`, `ratificacion.acto: ""`, `custodios: []`**. No existe ratificación vigente en ese documento. Producto no autorizado para release, rollback/purga no autorizados.
- No hay modificación de política de producción `catalogo-qg.yaml` / `politica_qg.py` en la implementación R19. No se activa la propuesta de QG-02.
- El ejecutor reportó pruebas focalizadas 57/57, 35/35, 26/26 puertas y CI 25/25 del commit 515f196. Esto demuestra señales de progreso, **no reemplaza examen de seguridad de la lógica de autoridad**.

## Reconocimiento del avance

**AUTH-01 (alcance parcial):** `registro_en_vigor()` exige `RATIFICADO` y una referencia declarada; `verificador_desde_registro()` solo entrega verificador si `VerificadorActosGit.en_vigor()` lo confirma. Un registro `PROPUESTA` no se activa por presencia. Esto responde correctamente al defecto base de R18.

**AUTH-02 (alcance parcial):** `_resuelve_autoridad()` contrasta el identificador canónico y alias en el registro, impidiendo identidades no reconocidas y ambiguas a ese nivel.

**AUTH-03 (alcance parcial):** `_valida_contrato_acto()` requiere `ACTO:RATIFICACION`, `ACCION:RATIFICAR`, `ESTADO:RATIFICADO` y coincidencias del alcance con los campos esperados. Los consultivos no satisfacen ese contrato.

**AUTH-04 (alcance parcial):** la custodia se presenta como segundo commit distinto y prohíbe operaciones destructivas dentro de su propia acta. Esto no constituye permiso para archivar/trasladar/purgar y está correctamente declarado.

No obstante, **la certificación de autoridad preactivación aún requiere cambios** por las brechas siguientes.

## Hallazgos nuevos con evidencia de código

**QA-R19-AUTH-05 — P1, una autoridad no designada puede pasar como custodio.** En `verificador_actos.py::_valida_contrato_custodia` se construye `admitidos = set(self.custodios) | set(self.autoridades)`. Por ello **cualquier autoridad registrada** es admitida como custodio incluso cuando `custodios: []`, contrariando el requisito expresamente declarado de designación por DEC-04. Hay prueba para un custodio desconocido, pero no la negativa **autoridad registrada no designada / lista de custodios vacía**. Reparar con autorización específica y explícita por ID de custodio (o delegación formal verificada); sin designación, `BLOCKED`.

**QA-R19-AUTH-06 — P1, no se acredita identidad real del custodio que suscribe el acta.** `verificar_custodia()` ejecuta `_identidad_coincide(autoridad, referencia)` usando la **autoridad de la decisión**, no la identidad del `CUSTODIO` declarado dentro del acta. La lista `custodios` solo contiene strings; no declara ni verifica por sí misma identidad Git y canal del custodio. Una autoridad puede publicar un segundo commit, autodenominar `CUSTODIO: custodio-1` y, por el contrato actual, superar el chequeo aun cuando ese custodio no haya firmado. Reparar con identidad/canal/fuente de autoridad del custodio independiente, o contrato de delegación explícita autorizado por el propietario y verificado. Añadir negativo: acta con nombre de custodio válido pero autor/canal ajeno al custodio.

**QA-R19-AUTH-07 — P1, ratificación del registro no exige todo el contrato de acta que declara.** En `VerificadorActosGit._evaluar_vigor()` se comprueban `ACCION`, `ESTADO`, `OBJETO`, `VERSION` y autor parcial, pero **no `ACTO: RATIFICACION`**, ni `FECHA` en el contenido del commit, ni correspondencia explícita de fecha/canal con el registro. El propio `autoridades-de-decision.yaml` especifica `ACTO: RATIFICACION` y `FECHA`. Poner exigencia estricta de contrato de acta del registro en vigor, comprobar coherencia de campos y evitar que un commit con solo los otros campos activos baste. Añadir tests negativos de ACTO ausente/equivocado y FECHA ausente/contradictoria.

**QA-R19-AUTH-08 — P2, alias legítimo rechazado por la política previa.** En `politica_certificacion_compuesta.py::_motivos_decision`, `autoridad != firmante` genera `IDENTIDADES_CONTRADICTORIAS` **antes** de que `_resuelve_autoridad()` pueda normalizar alias. Contradice la promesa de que `firmante` pueda ser alias registrado. Normalizar ambos contra la misma fuente confiable sin aceptar alias libres; añadir positivo alias autorizado y negativo alias de otra autoridad, en el **evaluador compuesto**, no solo a nivel del verificador.

**QA-R19-AUTH-09 — P2, vigencia temporal incompleta.** `_valida_contrato_custodia()` valida la forma `inicio/fin` pero solo rechaza `fin < hoy`. Una custodia con inicio futuro y fin posterior, o intervalo inicio > fin, puede aprobar. Exigir `inicio ≤ fecha_evaluación ≤ fin`, fechas ISO reales y `inicio ≤ fin`; pruebas de vigencia futura, invertida y fecha inválida.

**QA-R19-AUTH-10 — P2, claves de acta repetidas o contradictorias.** `_campos()` almacena una lista por campo; `_exige()` consume únicamente `valores[0]`. Mensajes con `ACCION: RATIFICAR` y segunda línea `ACCION: REVOCAR`, o `ESTADO: RATIFICADO` y `ESTADO: REVOCADO`, no se rechazan por ambigüedad. Exigir unicidad o un parser de acta estrictamente tipado; negativo para duplicados incluso cuando la primera ocurrencia es válida.

**QA-R19-AUTH-11 — riesgo por definir, revocación sobrevenida.** Los tests de estados comprueban que un *único acto* cuyo `ESTADO` es `REVOCADO` no ratifica. No hay mecanismo comprobado para invalidar un acto **antes RATIFICADO y después revocado por un commit posterior** en el canal. Especificar la fuente de revocaciones, precedencia e instantánea temporal; si se promete revocabilidad real, implementarla y probar ratificación→revocación→BLOCKED. Si no entra al contrato del release, declarar la limitación al propietario, sin fingir que los tests actuales cubren esa secuencia.

**Frontera de confianza no cerrada por código:** `identidad_git: {}` en el registro propuesto significa que `_identidad_coincide()` retorna `True` para cualquier autor. Además, ejecutor y propietario comparten capacidad de push según documentación. El canal `proposal/...` es **administrativo, no una prueba criptográfica de voluntad del dueño**. Decisión de segregación del canal, firmante autenticado y permisos bajo DEC-03/04 antes de ratificación. No pedir al ejecutor que se atribuya autorización del propietario.

## Decisiones, trazabilidad y release

- **DEC-02 (QG-00/01):** recomendar B con I2-a + COST-a, pero el propietario debe autorizar concretamente límites de latencia, compatibilidad, I1–I5, métricas 5→3 cruces y 10→0 divergencias, sin tocar snapshot/baseline. Implementarla requiere un nuevo SHA de producto y recertificación; el código de B aún no está implementado.
- **DEC-03 (QG-02):** contrato compuesto C puede ser opción fundada, pero queda en `PROPUESTA`; **no ratificar el registro de autoridades hasta resolver AUTH-05/06/07 y el modelo de identidad/custodia**, ni activar política de producción por declaración.
- **DEC-04:** preservar 66 archivos y sus hashes; nombrar custodio y autoridad confiable. **Custodia ≠ permiso de archivo, traslado o purga**; cada operación requiere otro acto. Ninguna operación destructiva está autorizada.
- **DEC-01/05/06:** en espera, respectivamente Constitución, historia y release; no inferir ratificación de preferencias consultivas.
- **QG-00/01=BLOCKED**, **QG-02=BLOCKED**, **QG-03..06=PASS reportado por recibos** para `015b776`, **QG-07=BLOCKED** por prerrequisitos y aprobación; la CI 515f196 sí pasó y no es el motivo principal de bloqueo actual.
- **No fusionar**, taggear, publicar release, reescribir historia, ampliar baselines ni destruir el backup.

## Continuidad recomendada

1. **El ejecutor puede** corregir los defectos preactivación QA-R19-AUTH-05..10 con pruebas negativas en repositorios descartables; investigar y resolver/explicitar la revocación. Conservar el registro en `PROPUESTA` y política de producción intacta.
2. Publicar nuevo HEAD y evidencia focalizada, pruebas de integración y CI; no repetir automáticamente la suite congelada si producto/wheel/tree continúan iguales.
3. Someter las correcciones a nuevo QA independiente.
4. Después de QA, el propietario decidirá DEC-02 (B o alternativa), DEC-03 (C y canal/autoridades), DEC-04 (custodio, preservación y actos operativos). No usar este dictamen como autorización del propietario.

**Veredicto formal:** `QA_R19=ACCEPTED_AS_DESIGN_PROGRESS_WITH_FINDINGS`; `AUTH_05_06_07=P1_PRE_ACTIVATION`; `AUTH_08_09_10=P2_PRE_ACTIVATION`; `AUTH_11=DECISION/CONTRACT_GAP`; `AUTHORITY_REGISTRY=PROPUESTA`; `RELEASE=BLOCKED_OWNER_AND_QA`. **Ningún PASS de pruebas focalizadas autoriza ratificar ni publicar.**

