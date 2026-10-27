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
  del camino de proceso ingenuo es ~60× el actual). **Propuesta sustentada
  (R17): I2-a** (publicar la superficie de mantenimiento en la wheel, la
  única que acredita el producto distribuido) **+ COST-a** (superficie ligera
  de baseline, que devuelve el audit a su orden de magnitud), con
  **umbral de latencia ≤ 5 s por audit**, **ventana de deprecación de una
  versión** y rollback por commit (PLAN-B §12.3-§12.4). Sin ratificación, el
  ejecutor NO ejecuta nada.
- **Alcance exacto de autorización (lo que la firma habilita y lo que no):**
  habilita **solo** la alternativa **B** con **I2-a** + **COST-a**, el
  umbral ≤ 5 s, la ventana de una versión, el criterio de éxito 5→3 cruces y
  10→0 divergencias **sin tocar el snapshot ni ampliar la baseline**, y la
  lista de pruebas I1–I5 del §6.1 del plan. **No habilita:** tocar el
  producto congelado `015b776` (cualquier cambio exige SHA nuevo y
  re-certificación), re-tomar el snapshot, modificar `catalogo-qg.yaml` /
  `politica_qg.py` (eso es DEC-03), ni mover datos (DEC-04).
- **Operaciones permitidas después de ratificar:** implementar el puerto de
  datos y proceso (núcleo), publicar la superficie de mantenimiento del dueño
  (I2-a), publicar la superficie ligera de baseline de `vault_smoke`
  (COST-a), migrar la fachada a consumir el puerto conservando la compat
  deprecada una versión, y re-certificar (26 puertas, suite, E2E desde wheel,
  CI del SHA nuevo, recibos, QA).
- **Criterios de rollback:** por commit (plan §8): el puerto es aditivo y la
  fachada conserva `_control_ap40/42/43` durante la ventana; revertir al
  commit previo al consumo del puerto deja el audit funcionando por el
  camino viejo. Si el puerto falla en producción: volver al commit 1 (el
  puerto existe y nadie lo consume) y medir de nuevo.
- **Quality Gates afectados:** QG-00 (identidad/reconciliación), QG-01
  (arquitectura: `off_port_total` 5→3 y reconciliador 10→0), QG-03/05/06
  (suite, paridad y E2E desde la wheel con la nueva superficie) y QG-07
  (CI del SHA nuevo).
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
  separadas A/B/B' y las tres opciones) y §5 (propuesta de diff **sin
  aplicar**); recibos QG-02 del candidato; ejecutable de referencia
  `audits/fase2/politica_certificacion_compuesta.py` con **27 pruebas
  fail-closed** (`tests/test_politica_certificacion_compuesta.py`).
- **Criterio de ratificación exigido (R17, QA-R16-QG02-01/02):** una
  decisión de residuo solo vale si es **formal**: identificador, estado
  `RATIFICADO`, firmante, fecha ISO, **referencia inmutable (SHA de 40
  hex)**, alcance que COINCIDE con el residuo concreto (id, norma, ruta y
  huella) y vínculo con la custodia verificada. Una referencia de texto libre
  no es firma; `PENDING`, `NOT_GIVEN`, campos vacíos, decisiones ajenas o
  registros mal formados dejan la puerta **BLOCKED**. La coherencia de la
  evidencia (conteo presente, entero, no negativo, array presente y
  consistente con el conteo, `completo: true`, controles ejecutados, SHA
  coincidente) es condición previa: una contradicción interna **nunca**
  produce PASS. Un escape nuevo sigue siendo **FAIL**.
- **Alternativas:** **A** solo sandbox; **B** solo runtime (debilita la
  detección: no recomendada); **C** compuesto: runtime limpio + ausencia de
  efectos externos nuevos + registro diferenciado del residuo histórico.
- **Riesgos:** B normalizaría «limpiar el entorno de test» como si subsanara
  el escape (lo que el dictamen prohíbe); C exige redactar la política con
  tests negativos antes de aplicarla.
- **Impacto:** desbloquea (o no) la evaluación de QG-02 junto con DEC-04.
- **Costos:** C: redacción de la política ejecutable + tests + someter a QA
  (≈ una ronda corta). R17 deja el ejecutable y los tests listos: la
  ratificación no requiere escribir código nuevo, solo el acto y el diff
  formal de §5 del dosier.
- **Recomendación:** **C**, por las tres razones del dosier §3, **con el
  criterio de ratificación formal de arriba incorporado** (la preferencia
  registrada por el propietario — `cc05eab` — sigue siendo preferencia, no
  ratificación).
- **Estado de autoridad (R19, QA-R18-AUTH-01..04):** la propuesta separa ya
  las cuatro capas: **esquema** (forma de la decisión), **existencia y
  contenido del acto** (commit real, alcanzable por el canal y con un
  CONTRATO de acta explícito: tipo, acción expresa, estado, decisión,
  autoridad, alcance, residuo, norma, ruta, huella, fecha y canal),
  **identidad y autorización** (un identificador único de autoridad:
  `autoridad` canónico y `firmante` alias, con correspondencia obligatoria) y
  **estado efectivo** (el registro tiene que estar EN VIGOR: `estado:
  RATIFICADO` más un acto de ratificación propio, existente y alcanzable;
  `PROPUESTA`/`DRAFT`/`PENDING`/desconocidos se rechazan y la mera presencia
  de autoridades no pone nada en vigor). La custodia es un **segundo acto**
  con contrato propio (custodio admitido, autoridad, id, residuo, norma, ruta,
  huella, operaciones autorizadas, vigencia temporal, canal) y **no autoriza
  archivar, trasladar ni purgar** (eso exige actos independientes de DEC-04).
  Mecanismo probado con objetos git reales en un repositorio descartable
  (**57 pruebas**: 32 de esquema/coherencia + 25 de autoridad; los negativos
  cubren registro no ratificado, autoactivación, acta consultiva, estados
  PROPUESTO/CONSULTADO/RECHAZADO/REVOCADO, alias contradictorio, custodio no
  admitido, custodia expirada y custodia con operaciones destructivas).
  **Límite declarado:** ejecutor y propietario comparten identidad git y
  permisos de push, así que el canal es un control **administrativo**, no
  criptográfico — el propietario debe decidir sobre custodia y permisos del
  canal antes de ratificar (queda como decisión explícita en DEC-03/DEC-04).
- **Alcance exacto de autorización (lo que la firma habilita y lo que no):**
  habilita **solo** aplicar la opción C al QG-02 de producción: el diff
  propuesto del dosier §5 (catálogo, política, colector y tests) y el
  verificador de actos con el registro que el propietario declare.
  **No habilita:** ratificar el residuo AP-36 (eso es DEC-04), excepcionar
  ninguna violación, ni tocar el producto congelado.
- **Operaciones permitidas después de ratificar:** redactar el diff formal
  de catálogo/política/colector, añadir los negativos de integración, aplicar
  el cambio, reemitir los recibos QG-02 con el veredicto compuesto y
  someterlo a QA antes de considerarlo conforme.
- **Criterios de rollback:** el cambio de política es reversible por commit
  (el catálogo y la política vuelven a su estado anterior y el evaluador
  anterior sigue vigente); mientras el residuo no esté decidido, el
  veredicto compuesto BLOCKED y el QG-02 permanece bloqueado — no hay estado
  intermedio que permita un PASS accidental.
- **Quality Gates afectados:** QG-02 (sujeto y contrato), y por arrastre
  QG-07 (que exige QG-00..06).
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
- **Actos separados (R19):** la autorización se puede dar por ACTOS, no de
  golpe, y cada uno lleva su propia evidencia y su propia reversión:
  1. **PRESERVACIÓN** (lectura + hashing + acta de inventario): ya hecha en
     lectura (R14/R15); es inocua y no requiere autorización para repetirse.
  2. **CUSTODIA** (nombrar quién responde del residuo, en qué canal publica
     sus actos y con qué operaciones): requiere que el propietario designe
     al custodio y lo declare en el registro (`custodios` + canal). Sin eso,
     el residuo queda sin fuente de autoridad y QG-02 BLOCKED. El contrato
     del acta de custodia (R19, AUTH-04) exige custodio, autoridad, id,
     residuo, norma, ruta, huella, operaciones, vigencia, canal y commit, y
     **no autoriza archivar, trasladar ni purgar**.
  3. **ARCHIVO** (crear el archivo de preservación y verificarlo contra los
     hashes del apéndice A): requiere autorización expresa del custodio; no
     toca el original.
  4. **TRASLADO / PURGA** (retirar el original): requiere autorización
     **separada** de la del archivo, con destino, plan de recuperación y
     evidencia previa; nunca implícita.
- **Alcance exacto de autorización (lo que la firma habilita y lo que no):**
  habilita **solo** los actos que se nomeen en la firma, con su alcance
  (ficheros, destino, fecha). **No habilita:** purgar sin archivo, mover sin
  inventario previo, ni que la desaparición de la carpeta se cuente como
  certificación: la re-auditoría debe acreditar las postcondiciones.
- **Operaciones permitidas después de ratificar:** re-inventariar (solo
  lectura), generar el archivo y verificarlo, registrar el acta de custodia,
  y — solo con su acto propio — trasladar o purgar; después, re-auditar los
  escenarios A y B.
- **Criterios de rollback:** el archivo verificado ES el rollback: si el
  traslado o la purga se ejecutan y el archivo no restituye el inventario
  (66 ficheros, hashes del apéndice A), se restaura desde él y se anula el
  acto. Hasta la verificación del archivo, el original no se toca.
- **Efecto sobre QG:** QG-02 (escenario A) dejaría de tener la violación; la
  puerta se re-evaluaría con el verificador real, no con una exención.
- **Acción posterior:** la que el propietario elija, ejecutada por quien él
  designe (por defecto, el ejecutor SOLO para las opciones con autorización
  escrita en esta ficha).
- **Quality Gates afectados:** QG-02 (el hallazgo INC-0001 y, con DEC-03, el
  sujeto de certificación) y QG-07 por arrastre.

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
