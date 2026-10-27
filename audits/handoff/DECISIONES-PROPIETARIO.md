# Decisiones reservadas al propietario — fichas DEC-01..DEC-06

**Estado: ESPERANDO DECISIÓN.** Ninguna de estas fichas es una aprobación ni
ratifica nada por sí sola. Cada una termina en un espacio de decisión vacío.
El GOAL R14 (§10) define el contrato de estas fichas; los datos vienen de los
expedientes citados en cada una.

**Cómo usar este documento:** el propietario rellena el bloque «Decisión» de
cada ficha (elegir alternativa + fecha + firma o referencia al acta). Con la
decisión asentada, la acción posterior pasa al ejecutor o a QA según diga la
ficha. Mientras sigan vacías, los gates afectados conservan su estado
fail-closed (QG-00/QG-01/QG-02 BLOCKED; `liberable: false`).

---

## DEC-01 — Constitución arquitectónica

- **Situación:** `docs/architecture/CONSTITUCION-ARQUITECTONICA.md` está en
  estado DRAFT. El estándar opera con presupuestos y guardas (QG-00/QG-01)
  cuya autoridad última sería la Constitución; sin ratificar, su fuerza es la
  de una propuesta técnica coherente, no la de un contrato.
- **Causa:** fue redactada durante la fase de gobernanza y nunca se sometió a
  acto formal de ratificación.
- **Evidencia:** el propio documento declara su estado; los guardas que
  derivarían de ella están en verde (26/26 puertas), lo que demuestra
  consistencia interna, no autoridad normativa.
- **Alternativas:** (a) ratificar tal cual; (b) enmendar puntos concretos y
  ratificar la versión enmendada; (c) mantener DRAFT y declarar qué partes del
  estándar quedan sin amparo constitucional.
- **Riesgos:** (a/b) ninguno técnico conocido; (c) el release saldría con su
  marco normativo en DRAFT — el dictamen QA lo registraría como limitación del
  alcance.
- **Impacto:** normativo, no de código. Ninguna tool cambia.
- **Costos:** (a/b) una revisión de lectura; (c) cero, pero el coste se
  traslada al release (limitación documentada).
- **Recomendación:** (b) revisión puntual + ratificación: barata y cierra el
  marco antes del release.
- **Efecto sobre QG:** ninguno directo (no hay gate de Constitución); afecta
  al alcance que QA puede conceder en REL-08.
- **Acción posterior:** si (a/b): actualizar el estado del documento a
  ratificado con referencia a la decisión; si (c): registrar la limitación en
  el manifiesto de release.

**Decisión:** ─── (ratificar / enmendar / mantener DRAFT) · Fecha: ───

---

## DEC-02 — Divergencias DIV-01..10 y los dos cruces a eliminar

- **Situación:** el reconciliador Archify reporta 10 divergencias sin aceptar
  (DIV-01..10, una causa raíz común: la composición se movió a la fachada
  `vault_norms` en `667a6a5` y el snapshot `f049b1bd` es anterior) y el
  registro declara `a_eliminar` (fecha límite 2027-06-30) los pares
  `gobernanza → meta_toolkit` y `gobernanza → autoria`. QG-00/QG-01 BLOCKED
  mientras no haya ratificación.
- **Causa:** deuda arquitectónica declarada y vigente + un inventario de
  snapshot desfasado; ninguna de las dos cosas se cierra sola.
- **Evidencia:** `divergencias-archify.yaml` (DIV-01..10), `QA-RC-03-CRUZES.md`
  (análisis A/B/C), `PLAN-B-MIGRACION-CRUZES.md` (plan ejecutable con criterio
  de independencia I1–I5, §6.1) y el apéndice de identidad y coste de este
  mismo plan (§11, añadido en R14).
- **Alternativas:** **A** composición desde el meta-toolkit — descartada por
  dirección (crearía el cruce que hay que eliminar); **B** migración
  compatible por etapas hacia un puerto de datos+proceso en el núcleo, con
  compat deprecada una versión — recomendada; **C** excepción formal con
  plazo, riesgo y dueño.
- **Riesgos de B:** R1–R6 del plan (control que deja de ejecutarse, evidencia
  de distinta forma, coste de tres procesos, cruce nuevo inverso, baseline,
  ruptura de consumidores) — cada uno con su mitigación y prueba.
- **Impacto:** QG-00/QG-01 vuelven a ser evaluables; `off_port_total` baja de
  5 a 3; el reconciliador pasa a verde SIN tocar el snapshot.
- **Costos:** implementación ≈ 7 commits pequeños (§7 del plan) + coste
  operativo **medido en R14** (PLAN-B §11.3: el camino de proceso ingenuo
  cuesta ~149 s frente a ~2,4 s del audit actual, dominado por AP-42) +
  re-certificación integral del SHA resultante. B queda **condicionada a dos
  enmiendas medidas**: la I2 (§11.2: las superficies de los dueños no están
  publicadas en la wheel) y la de coste (§11.3: superficie ligera de AP-42 o
  ejecución diferida en la puerta).
- **Recomendación:** **B**, condicionada a lo que el dictamen R13 exige:
  demostrar I1–I5 (la independencia semántica y operacional, no solo la
  ausencia de aristas) **y a las dos enmiendas medidas en R14** (§11.2 del
  plan: I2 — las superficies no están publicadas en la wheel; §11.3: el coste
  del camino de proceso ingenuo es ~60× el actual). Sin ratificación, el
  ejecutor NO ejecuta nada.
- **Efecto sobre QG:** desbloquea la evaluación de QG-00/QG-01 (no garantiza
  PASS: lo garantiza la ejecución con sus pruebas).
- **Acción posterior:** si B: ejecutar el §7 del plan con pruebas I1–I5 y
  re-certificación; si C: redactar la excepción formal (plazo, riesgo, dueño)
  y someterla a QA; si nada: QG-00/QG-01 siguen BLOCKED.

**Decisión:** ─── (A / B / C) · Fecha: ───

---

## DEC-03 — Contrato de QG-02: sujeto de certificación

- **Situación:** el expediente mide dos escenarios que no se sustituyen:
  runtime limpio (producto, 0 violaciones) y sandbox canónico (desarrollo,
  1 violación: el residuo externo AP-36). Falta ratificar QUÉ certifica la
  puerta.
- **Causa:** el contrato original de QG-02 no distinguió los dos sujetos; la
  propuesta dual (`POLITICA-CERTIFICACION-PRODUCTO.md`) no está aplicada.
- **Evidencia:** `QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md` §1 y §3 (mediciones
  separadas A/B/B' y las tres opciones); recibos QG-02 del candidato.
- **Alternativas:** **A** solo sandbox; **B** solo runtime (debilita la
  detección: no recomendada); **C** compuesto: runtime limpio + ausencia de
  efectos externos nuevos + registro diferenciado del residuo histórico.
- **Riesgos:** B normalizaría «limpiar el entorno de test» como si subsanara
  el escape (lo que el dictamen prohíbe); C exige redactar la política con
  tests negativos antes de aplicarla.
- **Impacto:** desbloquea (o no) la evaluación de QG-02 junto con DEC-04.
- **Costos:** C: redacción de la política ejecutable + tests + someter a QA
  (≈ una ronda corta).
- **Recomendación:** **C**, por las tres razones del dosier §3.
- **Efecto sobre QG:** QG-02 sigue BLOCKED hasta ratificación + resolución del
  residuo (DEC-04) o registro diferenciado si C se ratifica.
- **Acción posterior:** si C: proponer el cambio formal de catálogo/política
  con tests; aplicar solo tras aprobación.

**Decisión:** ─── (A / B / C) · Fecha: ───

---

## DEC-04 — `vault-backups` externo (residuo AP-36)

- **Situación:** existe `vault-backups/` dos niveles por encima del vault,
  fuera del repo, con UN snapshot de junio de 2026 (66 ficheros, ~834 KiB,
  contenido regenerable salvo artefactos históricos). La auditoría del sandbox
  lo reporta como la única violación abierta (INC-0001, crítica,
  `decision_required: true`).
- **Causa:** una operación de backup del toolkit con ubicación por defecto
  fuera del vault (junio 2026). El código actual ya no emite ahí; es residuo.
- **Evidencia:** ficha completa con inventario, hashes, fechas y riesgos en
  `QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md` §2 y apéndice A.
- **Alternativas:** (a) conservar donde está (QG-02-A sigue BLOCKED); (b)
  moverlo a una ubicación acordada con inventario antes/después registrado;
  (c) archivar (ZIP verificado contra los hashes del apéndice) y luego purgar
  el directorio; (d) purgar sin archivo (no recomendada: pierde la única copia
  del estado de junio).
- **Riesgos:** datos: bajos (contenido regenerable salvo el trace histórico);
  trazabilidad: medios si se mueve sin registro; certificación: QG-02-A
  bloqueada mientras exista en su ubicación actual.
- **Impacto:** desbloquea (o no) la violación abierta del expediente.
- **Costos:** (b/c) minutos + registro; (a) cero pero mantiene el bloqueo;
  (d) cero + pérdida.
- **Recomendación:** (c) archivar con verificación de hashes y después purgar,
  dejando el acto asentado aquí — solo si el propietario de los datos lo
  autoriza. **El ejecutor no toca el directorio sin esta decisión.**
- **Efecto sobre QG:** QG-02 (escenario A) dejaría de tener la violación; la
  puerta se re-evaluaría con el verificador real, no con una exención.
- **Acción posterior:** la que el propietario elija, ejecutada por quien él
  designe (por defecto, el ejecutor SOLO para las opciones con autorización
  escrita en esta ficha).

**Decisión:** ─── (a / b / c / d + ubicación o archivo acordado) · Fecha: ───

---

## DEC-05 — Historia publicada con rutas y nombre de cuenta

- **Situación:** la auditoría de exposición histórica (R01/R06) verificó 52
  commits considerados bajo los prefijos de evidencia, 10 con exposición
  (rutas absolutas locales y nombre de cuenta en logs), **0 blobs íntegros**
  inspeccionados; sin credenciales detectadas.
- **Causa:** logs de evidencia publicados con rutas del anfitrión antes de que
  existiera el saneamiento sistemático (`comprobar_saneamiento.py`, hoy en el
  pre-commit y en los recibos).
- **Evidencia:** `audits/fase2/auditar_exposicion_historica.py` + su informe;
  el dictamen R06 (H-F2-01 cerrado en su alcance, OBS-R06-03 sobre cobertura).
- **Alternativas:** (a) conservar la historia tal cual con este riesgo
  documentado; (b) saneamiento histórico (reescritura) con procedimiento
  autorizado.
- **Riesgos:** (a) el riesgo documentado (exposición de rutas y nombre de
  cuenta, sin credenciales detectadas); (b) reescritura de SHA de TODOS los
  commits posteriores, invalida clones y recibos históricos, y exige
  re-firmar la cadena de evidencias del release.
- **Impacto:** (b) rompería la trazabilidad de SHA que QG-00 exige; (a) no
  toca nada.
- **Costos:** (a) cero; (b) alto (re-certificación completa + coordinación de
  clones).
- **Recomendación:** (a) conservar con riesgo documentado: sin credenciales
  detectadas, el coste de (b) supera su beneficio; el saneamiento preventivo
  (hoy) evita nuevas exposiciones.
- **Efecto sobre QG:** ninguno inmediato; (b) invalidaría recibos vigentes.
- **Acción posterior:** (a) mantener el saneamiento preventivo y la nota de
  riesgo en el manifiesto de release.

**Decisión:** ─── (a / b) · Fecha: ───

---

## DEC-06 — Autorización del release (post QA)

- **Situación:** con QA favorable (REL-08) y puertas efectivas, falta el acto
  expreso del propietario que autoriza distribuir (REL-09) y, después,
  publicar (REL-10). CI verde NO es autorización.
- **Causa:** el gobierno del release reserva la publicación al propietario.
- **Evidencia:** matriz REL-00..13 del informe de readiness (estado medido);
  dictamen QA vigente; manifiesto del candidato.
- **Alternativas:** aprobar la distribución del candidato identificado;
  rechazarla; aprobar con condiciones (alcance limitado, p. ej. sin
  capacidades no ejercidas por el E2E: `plan`, `batch`, `--verify-integrity`,
  SSE/HTTP, exit 130).
- **Riesgos:** publicar con riesgos residuales no tratados. **TD-0008 ya no
  es uno de ellos en su forma original**: el `--clean` transaccional está
  implementado (commit `cc85491`: preflight, cuarentena verificada por hash,
  `--confirm`/`--dry-run`, rollback) con 22 tests, pasos E2E y la misma
  implementación en la wheel distribuida; el registro de deuda quedó
  reconciliado (QA-R14-DOC-01). La aceptación QA explícita de ese cierre
  sigue pendiente de dictamen. Las capacidades del PRD sin acreditación caso
  por caso (`plan`, `batch`, `--verify-integrity`, SSE/HTTP, salida 130)
  siguen como límite de alcance declarado.
- **Impacto:** habilita REL-10..REL-13 (publicación, activación, seguimiento,
  relanzamiento).
- **Costos:** los de publicación + soporte del alcance aprobado.
- **Recomendación:** decidir DESPUÉS del dictamen QA de esta ronda; si la
  aprobación es con condiciones, listarlas aquí y reflejarlas en el alcance
  del manifiesto.
- **Efecto sobre QG:** ninguno (es posterior a los gates); habilita el tag y
  el release.
- **Acción posterior:** si se aprueba: publicar según el manifiesto (tag,
  release, hashes, SBOM); si se rechaza: registrar motivos y volver a
  planificación.

**Decisión:** ─── (aprobar / aprobar con condiciones / rechazar) · Fecha: ───


---

# Anexo consultivo — propuestas DEC-02=B, DEC-03=C y DEC-04=PENDING

**Registrado como propuesta del propietario:** 2026-10-26 (fecha local de la consulta).  
**Origen documental:** rama `work/release-cli-mcp-20261025`, SHA `e0fc775551217ee0a778ca3dece0da3f0a63ba38`.  
**Tipo de registro:** `OWNER_PREFERENCE_PROPOSED`. **No constituye ratificación, waiver, autorización de implementación ni decisión de release.**  
**Estado de las casillas oficiales DEC-02/03/04:** **SIN FIRMAR**, preservadas arriba.  
**Alcance de este anexo:** registra opciones preferidas y sus condiciones de elegibilidad para un acto formal posterior. No sustituye las fichas, la Constitución DRAFT, las pruebas, la política QG ni las evidencias.

| Ficha | Opción propuesta por el propietario | Estado jurídico/técnico en este registro | Gate y efecto |
|---|---|---|---|
| **DEC-02** | **B** — migración compatible por etapas para eliminar los cruces `gobernanza → meta_toolkit` y `gobernanza → autoria` | **PREFERENCIA PROPUESTA, CONDICIONADA**. No se autorizó ejecutar el plan ni aceptar DIV-01..10. | QG-00/QG-01 siguen `BLOCKED`; elegir B no elimina dependencias ni reconcilia por sí solo el snapshot. |
| **DEC-03** | **C** — certificación compuesta: runtime limpio y sandbox canónico medidos por separado; detectar efectos externos nuevos y registrar el residuo histórico | **PREFERENCIA PROPUESTA, CONDICIONADA**. No se autorizó modificar `catalogo-qg.yaml`, `politica_qg.py` ni aceptar AP-36. | QG-02 sigue `BLOCKED`; runtime limpio `PASS` no sustituye al audit del sandbox. |
| **DEC-04** | **pending** — no se elige todavía conservar, trasladar, archivar o purgar `vault-backups` | **SIN DECISIÓN**. No hay permiso para tocar datos ni para aceptar riesgos. | AP-36 y el estado de certificación asociado permanecen abiertos; QG-02 no se desbloquea por este registro. |

## Condiciones exactas de DEC-02=B antes de cualquier implementación reservada

1. **Arquitectura real, no cosmética.** El destino es eliminar los dos pares de dependencia indebida sin reintroducirlos mediante subprocess, registro dinámico ni imports opacos. Conservar `objetivo: a_eliminar` y la fecha límite vigente **2027-06-30**; no ampliar baselines, cambiar `ratificado: false`, modificar el snapshot histórico ni aceptar DIV-01..10 mediante waiver implícito.
2. **I1–I5 obligatorios** según `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` §6.1: independencia semántica, operación desde la wheel instalada, retorno observable, efectos laterales declarados y fallo seguro si un verificador no existe. Verificar equivalencia funcional CLI/MCP, estados TD-0003, seguridad, reconciliador y regresión integral.
3. **Enmienda I2 por decidir expresamente.** El puerto de §3 tal cual no funciona en la wheel: `vault_mcp_catalog`, `vault_smoke` y `vault_voice` son herramientas de mantenimiento no publicadas como superficie instalada. El propietario debe elegir **(I2-a)** publicar entry points compatibles en la wheel, **(I2-b)** restringir explícitamente el puerto a una distribución de mantenimiento sin atribuirle compatibilidad con terceros, o **(I2-c)** explorar registro en proceso con arista declarada y sus límites. No elegir por inferencia; preferir demostrar I2-a si se desea acreditar el producto distribuido.
4. **Enmienda de costo por decidir expresamente.** Medición R14: subprocesos ingenuos **≈149,4 s** frente a audit actual **2,42 s** (~60×), principalmente AP-42 `vault_smoke --check`. Antes de implementar B, seleccionar **(COST-a)** interfaz ligera de baseline publicada por el dueño o **(COST-b)** ejecución diferida con nuevo contrato de estados, o analizar otra arquitectura bajo los mismos criterios; fijar umbral de latencia aceptable y registrar benchmark antes/después. No ejecutar el camino ~60× por defecto ni falsear `ejecutado` cuando solo se pospone.
5. **Orden y rollback.** Concretar interfaces, impacto y plan por commits reversibles; mantener compatibilidad de las superficies públicas y una ventana de deprecación acotada. Acreditar I1–I5, 26 puertas, suite, wheel E2E y matriz CI del SHA resultante. Hasta lograrlo, la expectativa `off_port_total: 5 → 3` y divergencias `10 → 0` es **objetivo**, no resultado.
6. **Autoridad reservada.** Requiere acto expreso del propietario identificando **B, subopción I2, subopción de costo, criterios de aceptación, límites de compatibilidad, fecha y referencia de ratificación**. Después, el ejecutor podrá implementar bajo ese alcance y QA revisará la evidencia sin sustituir al propietario.

## Condiciones exactas de DEC-03=C antes de modificar la política QG-02

1. **Dos sujetos, resultados separados.** Auditar el runtime instalado nuevo y el sandbox canónico del repo con el mismo estándar, guardar run/SHA, salidas y evidencia de cada uno. El primero acredita al consumidor; el segundo acredita ambiente, fixtures y efectos externos. No sustituir uno por el otro.
2. **Detección no degradada.** Un escape AP-36 NUEVO, una violación del runtime o un control AP-40/AP-42/AP-43 omitido o degradado impiden `PASS`. Los 13 defectos de semillas corregidos no son waivers. `NOT_RUN`/`BLOCKED` nunca equivalen a `PASS`.
3. **Residuo histórico separado, no perdonado.** `vault-backups` externo conserva su evidencia y severidad AP-36; se distingue de las emisiones nuevas sin borrar el hallazgo ni declarar que la auditoría original pasó. El dossier advierte que, **mientras DEC-04 siga sin resolver, QG-02 continúa BLOCKED** bajo la política actual y la propuesta estricta.
4. **Cambio reservado de contrato.** Preparar, sin aplicar, el diff propuesto de `POLITICA-CERTIFICACION-PRODUCTO.md`, `catalogo-qg.yaml`, `politica_qg.py`, colector y tests. Incluir negativas sobre escape nuevo, archivo histórico sin procedencia y control no ejecutado. La aprobación exige acto formal del propietario sobre el alcance y revisión QA; no alterar el catálogo para forzar verde.

## DEC-04=PENDING: reglas de preservación y decisión futura

- No borrar, mover, renombrar, comprimir, purgar ni modificar el directorio externo `vault-backups` o su manifiesto. No activar procedimientos de mantenimiento que lo alteren.
- La evidencia existente describe **66 archivos y 854.108 bytes** de un snapshot histórico de junio de 2026, con hashes en el expediente. Esa medición es **histórica**: antes de cualquier futuro movimiento hay que revalidar inventario, SHA-256, titularidad y destino mediante acceso solo lectura.
- Opciones futuras (a/b/c/d) siguen disponibles. Si se considera **c** (archivar y después purgar), el acto requiere autorización escrita del dueño de datos, destino explícito, comparación hash del archivo conservado, plan de recuperación y una autorización **separada** para la purga. Este anexo NO concede ninguna de esas autorizaciones.
- Mantener AP-36 documentado y QG-02 bloqueado o conforme a su evaluador vigente, sin transformar el riesgo en exención.

## Prerrequisitos y siguientes pasos permitidos

1. **Permitido ahora, sin acto reservado:** inspección de solo lectura, comparativas AS-IS/TO-BE, diseño de alternativas I2/costo, benchmarks en sandboxes descartables, propuestas de pruebas y borradores de cambios normativos **no aplicados**.
2. **Prohibido por este anexo:** editar `ratificado`, aplicar waivers, refactorizar el puerto con consecuencias reservadas, cambiar la política QG-02, modificar `vault-backups`, fusionar PR, tocar `main`, modificar historia o publicar release.
3. **Decisiones adicionales no inferidas:** DEC-01 (Constitución), DEC-05 (historia pública) y DEC-06 (autorización de distribución) permanecen exactamente como estaban, sin aprobación.
4. **Siguiente intervención del propietario:** elegir los detalles I2 y costo de DEC-02; delimitar y firmar el contrato C de DEC-03; decidir por separado qué hacer con DEC-04 y, posteriormente, el resto de autoridades de release. Registrar fecha/firmante/referencia sobre la ficha formal cuando exista acto inequívoco.

**Estado formal resultante:** `DEC-02=PROPOSED_B_CONDITIONAL`; `DEC-03=PROPOSED_C_CONDITIONAL`; `DEC-04=PENDING`; `OWNER_RATIFICATION=NOT_GIVEN`; `WAIVERS_RATIFIED=0`; `RELEASE_AUTHORIZED=false`. No modifica los estados de QG existentes ni la matriz de release.
