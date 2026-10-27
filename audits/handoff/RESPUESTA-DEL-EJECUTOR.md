# Respuesta del ejecutor a QA — R21 (AP-37 en Linux resuelto en causa y delegación acotada al residuo)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `e5220ff` (rama `qa/review-authority-r20-e0d0c75-20261027`) — `QA_R20=REQUIRES_CHANGES`; `AUTH12=OPEN`; `AP37_LINUX=FAIL`
- **SHA inicial:** `e0d0c754aa0897f23779aa67d6f0f36960fe3126` · **Producto congelado (sin modificaciones):** `015b7765b80cac21c6dcf859ae075d036cd01def` (tree `d190fd24…`)

```text
GOAL: RELEASE CLI + MCP PARA TERCEROS
RONDA: R21
ESTADO: BLOCKED_OWNER_DECISION — los dos P1 (AP-37 en Linux y AUTH-12) están
        corregidos en causa, con medición y pruebas negativas. El producto
        congelado NO se ha modificado (comprobado en la wheel). La política
        de producción y el registro de autoridades siguen SIN activar.
        GOAL ABIERTO; falta la CI del HEAD nuevo y el dictamen.

SHA INICIAL: e0d0c75
SHA FINAL: el commit de esta ronda (+ delta con la CI del HEAD)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def (SIN CAMBIOS)
PRODUCT_TREE_SHA: d190fd243567556e824795154b6fd44bd76309d5

QA-R20-CI-01 (AP-37 en Linux) — RESUELTO
  CAUSA RAIZ: `vault_graph` es idempotente por contrato: `atomic_write_json`
  CONSERVA el fichero cuando el documento es idéntico. Su ejemplo desnudo
  (`argv: []`) escribe solo si el grafo está desfasado; cuando ya está al
  día no escribe y AP-37 lo trataba como silencio, sin mirar el indicador
  que la tool SÍ publica (`written`, `unchanged`). El banco dependía del
  estado del sandbox en el momento del gate, y por eso el rojo solo apareció
  en la columna donde el grafo estaba al día (ubuntu-3.12).
  REPRODUCCION (Linux + Python 3.12, contenedor python:3.12-bookworm sobre
  el mismo árbol, sandbox descartable):
     · estado inicial: graph.json sha256 0ff3e206…cccd
     · PASADA 1 (grafo del checkout): `written: 1, updated: 1`; sha 7f2b24c5…b492
     · PASADA 2 (grafo ya regenerado): `written: 0, unchanged: 1, updated: 0`;
       sha IDÉNTICO 7f2b24c5…b492  → NO-OP LEGÍTIMO
     · CONDICION 3 (nota modificada, enlace roto añadido): `written: 1,
       updated: 1` (brokenLinks 11→12); sha 81e28cf1…375a → TRABAJO REAL
  Los otros 11 jobs del run no fallaron porque en ellos el grafo estaba
  desfasado y `vault_graph` escribió (verde por medida): el gate era
  dependiente del estado, no de la plataforma.
  CORRECCION (causa, sin volver AP-37 permisivo): clase NUEVA en
  `vault_noop_audit` — `IDEMPOTENTES_DECLARADAS` con el motivo MEDIDO y los
  indicadores EXIGIDOS (`written: 0` + `unchanged >= 1`). Reglas:
    · sin escritura + indicador exigido presente -> `noop_declarado` (verde,
      con la evidencia registrada);
    · sin escritura + indicador ausente -> ROJO (oculta el no-op);
    · escribió y declaró el no-op -> ROJO (idempotencia falsa);
    · escribió y lo dijo -> `medida` (como siempre);
    · tool no declarada que no escribe -> ROJO (sin cambios).
  `vault_smoke.run_one` viaja el envelope (`datos`) para poder comprobar los
  VALORES de los indicadores, no solo sus nombres.
  PRUEBAS: 21/21 en `tests/test_noop_audit.py`, con las negativas nuevas
  (no basta con no escribir; sin indicador -> rojo; idempotencia falsa;
  tool no declarada sigue roja) y el positivo del banco real.
  CI RUN: el del HEAD de esta ronda (abajo).

QA-R20-AUTH-12 (delegación) — RESUELTO
  CAUSA RAIZ: `_delega_verificada()` comprobaba que existiera `ALCANCE`, pero
  NO que ese alcance correspondiera al residuo evaluado; una delegación ajena
  podía custodiar otro residuo.
  CORRECCION: la delegación ahora acredita (1) delegante registrado y con
  canal; (2) alcance EXACTO contra el hallazgo —RESIDUO + NORMA + HUELLA—;
  (3) correspondencia acta ↔ configuración (`delega.alcance`); (4)
  procedencia desde canal del delegante o del delegado; (5) identidad del
  delegante cuando la declara; (6) VIGENCIA real (inicio ≤ hoy ≤ fin,
  invertida/futura/expirada rechazadas); (7) revocación aplicable al acta.
  SE MANTIENE DOCUMENTADO: identidad Git compartida y permiso de push
  compartido NO son autorización independiente.
  PRUEBAS NEGATIVAS (8, con commits reales en repos descartables): acta para
  OTRO residuo; canal ajeno; delegante no autorizado; delegado distinto;
  alcance vacío; alcance contradictorio con el registro; acta inexistente;
  delegación revocada; vigencia expirada.
  PRUEBA POSITIVA: acta válida para el residuo correcto -> la custodia acredita.

SUITE:   r14 vigente del producto (6334/13/0); NO reejecutada: el árbol
         empaquetado no cambió (ver análisis de impacto).
PUERTAS: 26/26 (afectadas; el gate `noop` incluido con su clase nueva)
CI:      ver SHA INICIAL/FINAL por corrida; la del HEAD se registra al concluir
RECIBOS: los del producto 015b776 siguen siendo suyos y no se trasladan
REGRESIONES: 101/101 focalizadas (34 verificador + 33 evaluador + 9
         delegación + 21 noop + manifiesto/copia/protocolo/política)
EVIDENCIAS: `%TEMP%\opencode\r21-medicion-linux.txt` (tres pasadas con sha256
         antes/después), `r21-noop-*.json`, wheel inspeccionada (706 ficheros:
         `vault_noop_audit` y `vault_smoke` NO viajan -> producto intacto),
         tests nuevos en `tests/test_delegacion_actos.py` y
         `tests/test_noop_audit.py`.

ANÁLISIS DE IMPACTO (producto congelado): los dos ficheros tocados,
`scripts/vault_noop_audit.py` y `scripts/vault_smoke.py`, son herramientas de
MANTENIMIENTO y **no están en la wheel** (comprobado contra
`vault_obsidian_architecture-41.23-py3-none-any.whl`: 0 ficheros para ambas;
`vault_graph`, el producto, sí viaja y NO se ha tocado). El árbol empaquetado
no cambia -> `015b776` sigue siendo el producto congelado y sus recibos/CI
no se transfieren al HEAD.

DEC-01: EN ESPERA (Constitución DRAFT; sin cambio)
DEC-02: PROPUESTA (B + I2-a + COST-a; ≤5 s; una versión; I1–I5; 5->3 y
        10->0 sin tocar snapshot ni baseline; rollback por commit)
DEC-03: PROPUESTA (C compuesta + registro/canal; verificador de autoridad con
        AUTH-01..12; sin aplicar a producción)
DEC-04: PENDING (custodio + archivo no destructivo; traslado y purga como
        actos SEPARADOS). Los 66 ficheros siguen intactos (854.108 B, 3/3
        hashes).
DEC-05: EN ESPERA (historia publicada)
DEC-06: SOLO tras QG efectivos y QA favorable

RIESGOS: canal administrativo (identidad/push compartidos); revocación
        depende de la misma fuente; registro en PROPUESTA; SSE/HTTP único
        NOT_RUN de la superficie; el no-op declarado exige mantener el
        indicador (hay test que lo vigila).
BLOQUEOS: DEC-01..06 sin firmar; QG-00/01/02 BLOCKED; dictamen del HEAD.
SIGUIENTE ACCIÓN: CI del HEAD -> si 25/25, dictamen QA; con DEC-02/03/04
        firmadas, implementar el alcance autorizado y recertificar.
SOLICITUD QA: revisión independiente del HEAD de esta ronda (AP-37 en Linux
        y AUTH-12 corregidos, producto intacto).

LIBERABLE: false — RELEASE_BLOCKED
```

## Decisiones listas para el propietario (sin ratificar)

| Decisión | Alternativa recomendada | Qué permite | Qué no permite |
|---|---|---|---|
| **DEC-02** | **B + I2-a + COST-a** | implementar la migración compatible según el plan (§7), con I1–I5, coste medido y rollback por commit | modificar arbitrariamente el producto congelado; tocar el snapshot o la baseline |
| **DEC-03** | **C, certificación compuesta** | someter la política y el **registro/canal de autoridades** a ratificación formal y aplicar el diff propuesto | eximir AP-36, aceptar actos no autenticados ni activar la política por declaración |
| **DEC-04** | **designar custodio y preservar** | acta de custodia con identidad/canal propios y archivo verificado no destructivo | trasladar o purgar (actos separados) ni certificar por la desaparición de la carpeta |

**DEC-01** (Constitución) DRAFT · **DEC-05** (historia) en espera · **DEC-06**
(release) solo tras QG efectivos y QA favorable. Ningún campo de decisión se ha
rellenado ni se ha atribuido al propietario.

---

# Respuesta del ejecutor a QA — R20 (custodio designado y con identidad propia, acta de ratificación completa, vigencia, duplicados y revocación)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `222094f` (rama `qa/review-release-cli-mcp-ab2e30c-20261027`) — `QA_R19=ACCEPTED_AS_DESIGN_PROGRESS_WITH_FINDINGS`; `AUTH_05_06_07=P1_PRE_ACTIVATION`; `AUTH_08_09_10=P2_PRE_ACTIVATION`; `AUTH_11=DECISION/CONTRACT_GAP`
- **SHA inicial:** `ab2e30c4cfb929e95c3c8ee4403aa640abfa8ac3` · **Producto congelado (sin modificaciones):** `015b7765b80cac21c6dcf859ae075d036cd01def` (tree `d190fd24…`)

```text
GOAL: RELEASE CLI + MCP PARA TERCEROS

ESTADO: BLOCKED_OWNER_DECISION — los seis defectos preactivación
        (AUTH-05..10) están cerrados en la PROPUESTA y la revocación
        (AUTH-11) está definida, implementada y probada en el canal
        declarado, con su límite escrito. El registro sigue en PROPUESTA;
        la política de producción NO se ha tocado; el producto congelado
        NO se ha modificado. **La CI del HEAD R20 (efae502) quedó 24/25 con
        un hallazgo ABIERTO en el gate `noop` (`vault_graph`), ajeno a la
        propuesta y no reproducible en esta máquina: ver el detalle abajo.**
        GOAL ABIERTO.
RAMA: work/release-cli-mcp-20261025
HEAD INICIAL: ab2e30c
HEAD FINAL: el commit de esta ronda (+ delta documental con la CI del HEAD)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def (SIN MODIFICACIONES)
PRODUCT_TREE: d190fd243567556e824795154b6fd44bd76309d5

HALLAZGO, CAUSA RAIZ, CAMBIO Y PRUEBA — uno a uno:
 AUTH-05  HALLAZGO: una autoridad registrada pasaba como custodio aunque
   `custodios: []`. CAUSA: `admitidos = set(custodios) | set(autoridades)`.
   CAMBIO: el custodio tiene que estar DESIGNADO expresamente (id + identidad
   + canal) en el registro; la lista de autoridades NO se une a la de
   custodios. Con `custodios: []` ninguna custodia acredita. PRUEBAS:
   `test_con_custodios_vacios_ninguna_custodia_puede_acentarse`,
   `test_una_autoridad_registrada_no_es_custodio`.
 AUTH-06  HALLAZGO: se comprobaba la identidad de la AUTORIDAD, no la de QUIEN
   FIRMA el acta; un custodio válido podía ser suplantado. CAUSA:
   `_identidad_coincide(autoridad, ...)` y `custodios` como lista de strings.
   CAMBIO: cada custodio declara `identidad_git` y `canales`; el acta la firma
   el custodio (se verifica su identidad y su procedencia) y, si hay
   delegación, exige un ACTA DE DELEGACION verificable con alcance. PRUEBAS:
   `test_un_custodio_que_no_firma_no_puede_ser_suplantado`,
   `test_una_delegacion_exige_acto_verificable_con_alcance`.
 AUTH-07  HALLAZGO: el acta de ratificación del registro no exigía todo el
   contrato (faltaban ACTO, FECHA en el contenido y la correspondencia de
   fecha/canal). CAUSA: `_evaluar_vigor` comprobaba ACCION/ESTADO/OBJETO/
   VERSION y autor. CAMBIO: contrato COMPLETO (ACTO: RATIFICACION, ACCION:
   RATIFICAR, ESTADO: RATIFICADO, OBJETO, VERSION, FECHA y CANAL
   coincidentes con lo declarado, identidad del ratificador). PRUEBAS:
   `test_el_acta_de_ratificacion_necesita_el_contrato_completo` (7 campos),
   `test_un_acta_de_ratificacion_con_fecha_contradicoria_no_entra_en_vigor`.
 AUTH-08  HALLAZGO: un alias legítimo se rechazaba por comparar cadenas antes
   de normalizar. CAUSA: `autoridad != firmante` en el esquema. CAMBIO: el
   esquema no compara cadenas; la normalización (y el rechazo de alias
   libres, ambiguos o de otra autoridad) la hace el verificador contra el
   registro. PRUEBAS: `test_un_alias_legitimo_se_normaliza`,
   `test_un_alias_desconocido_o_de_otra_autoridad_se_rechaza`,
   `test_un_alias_ambiguo_se_rechaza` y
   `test_en_el_evaluador_un_alias_legitimo_no_se_rechaza` (positivo y
   negativo EN EL EVALUADOR, como pedía el dictamen).
 AUTH-09  HALLAZGO: la vigencia solo rechazaba `fin < hoy`; una custodia con
   inicio futuro o intervalo invertido pasaba. CAUSA: validación parcial.
   CAMBIO: `inicio <= hoy <= fin`, fechas ISO reales y `inicio <= fin`.
   PRUEBAS: `test_una_vigencia_futura_invertida_o_invalida_se_rechaza`
   (4 casos: futura, invertida, fecha imposible, formato inválido).
 AUTH-10  HALLAZGO: `_campos` guardaba listas y `_exige` usaba `[0]`: un acta
   con `ACCION: RATIFICAR` y luego `ACCION: REVOCAR` pasaba. CAUSA: no había
   comprobación de unicidad. CAMBIO: `_exige` rechaza DUPLICADOS (aunque la
   primera ocurrencia sea válida) y propaga el motivo a todos los callers.
   PRUEBAS: `test_un_acta_con_campos_duplicados_se_rechaza` (ACCION, ESTADO,
   ACTO).
 AUTH-11  HALLAZGO: no había mecanismo para invalidar un acto antes
   RATIFICADO y luego REVOCADO. CAUSA: solo se miraba el ESTADO del propio
   acto. CAMBIO: se define la FUENTE de revocaciones (el canal declarado de
   la autoridad): un acta `ACTO: REVOCACION` + `ACCION: REVOCAR` +
   `REVOCA: <sha>` invalida el acto referenciado, y la evaluación vuelve a
   BLOCKED. PRUEBA: `test_ratificacion_luego_revocacion_deja_el_residuo_bloqueado`
   (ratifica -> acredita; revoca -> BLOCKED; nueva evaluación -> BLOCKED).
   LIMITE ESCRITO: la integridad de la fuente de revocaciones es el MISMO
   control administrativo que el canal; su incorporación al contrato del
   release queda pendiente de DEC-03 y no se improvisa autoridad.

PRUEBAS FOCALIZADAS: 34/34 en el verificador (16 de R20 + 18 recuperadas de
        R19, adaptadas al contrato nuevo: la reescritura había reducido la
        cobertura y se restauró — sin debilitar nada) · 33/33 del evaluador
        compuesto · 35/35 de manifiesto, copia, política QG y guard del
        protocolo · saneamiento exit 0 · doc_counts verde tras regenerar el
        recuento de tests (6426; sin pérdida neta de cobertura) · 26/26
        puertas (afectadas).
CI POR SHA (sin sustituir evidencia entre SHAs): 40442954197 (producto
        015b776) 25/25 · 40456389815 25/25 · 40464661392 failure 24/25
        (carrera de copia, corregida) · 40467869545 25/25 · 40472633327 25/25
        · 40474701480 25/25 · 40481751486 25/25 · 40488879515 (HEAD R19)
        25/25 · 40494674454 (delta R19 ab2e30c) 25/25 ·
        **40499964653 (HEAD R20 efae502): 24/25 — ROJO, 1 job** (ver abajo).

HALLAZGO ABIERTO (no se oculta): la corrida del HEAD R20 deja un job en rojo,
        `Validate Vault Spec (ubuntu-latest, 3.12)`, y NO por la propuesta:
        el paso `vault_gate --strict` dio 25/26 con el gate **`noop`** (AP-37)
        en rojo. El detalle del envelope acusa a **`vault_graph`** en
        `sin_escritura_sin_motivo` con su ejemplo desnudo (`argv: []`,
        `tool_ok: true`) y sin escritura observada en la ejecucion.
        CLASIFICACION: condicion de estado/plataforma, NO reproducida en esta
        maquina: el mismo chequeo `vault_noop_audit --ejecutado` en Windows
        pasa DOS veces seguidas (`ok: true`, `sin_escritura_sin_motivo: []`,
        `vault_graph` ni aparece). El comportamiento depende de si el grafo
        del sandbox ya esta al dia (si lo esta, el ejemplo no escribe, y AP-37
        lo exige declarado con su motivo medido: es el mismo patron que
        `vault_section_index`, ya declarado por idempotencia). No se ha
        "arreglado" con una declaracion a ciegas — seria un falso verde: la
        declaracion exige el motivo MEDIDO en la plataforma donde se observa y
        se comprueba en las dos direcciones (si luego escribe, el banco se
        pone rojo).
        SIGUIENTE ACCION (definida): reproducir en Linux la idempotencia del
        ejemplo desnudo de `vault_graph` (dos pasadas sobre la misma copia y
        comparacion de bytes del grafo); con la medida, o se le da un efecto
        determinista al ejemplo o se declara con su motivo; despues, nueva
        corrida del HEAD. Mientras tanto: el HEAD R20 NO tiene CI concluyente
        en verde y asi se declara.
SUITE:   r14 vigente para el producto congelado (6334/13/0); NO se ha
         reejecutado: el árbol y los contratos ejecutables del producto no
         han cambiado (solo audits/ y tests de la propuesta).
PUERTAS: 26/26 (r14, vigente)
E2E:     27/27 (r14, vigente)
WHEEL:   8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
SDIST:   1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656

MODELO DE CONFIANZA (GOAL R20 §5) — declarado sin adornos:
  1. La identidad git compartida y el permiso de push compartido NO son
     autorización independiente. En este repositorio el ejecutor y el
     propietario comparten cuenta y permisos: cualquier control que dependa
     solo de "quién hizo el commit" es un control SOCIAL, no técnico.
  2. Por eso el mecanismo no finge criptografía: acredita que EXISTE un acto
     verificable (commit real, alcanzable por un canal declarado, con contrato
     de acta, identidad declarada y alcance coincidente). La GARANTÍA de que
     ese acto emane del propietario depende de la integridad del canal.
  3. MECANISMO RECOMENDADO para separar la autoridad del propietario de la
     capacidad del ejecutor (PROPUESTA; no configurado por el ejecutor):
       a) CANAL PROTEGIDO: reglas de rama (rulesets) que impidan el push
          directo a la rama del canal; los actos entran por PR revisado o por
          una rama que solo el propietario puede escribir. Requiere
          administración del repositorio (propietario).
       b) IDENTIDAD VERIFICABLE: cuenta de mantenedor distinta para el canal,
          commits firmados (SSH/GPG) y verificación de firma exigida en la
          rama del canal. `git verify-commit` no requiere criptografía
          propia: usa la que el propietario configure.
       c) REGLAS DE CUSTODIA: un custodio designado con identidad y canal
          propios; la custodia NO autoriza archivar/trasladar/purgar
          (actos separados); y una regla de dos personas para ratificar el
          REGISTRO de autoridades (firmante + testigo) si el propietario la
          quiere.
     Nada de esto se ha configurado ni se configura sin su decisión.

EVIDENCIAS: `audits/fase2/verificador_actos.py` (contratos de acta,
        custodia y revocación) · `audits/fase2/autoridades-de-decision.yaml`
        (registro PROPUESTA: `custodios: []`, plantilla de designación y
        delegación) · `audits/fase2/politica_certificacion_compuesta.py`
        (esquema sin comparación de cadenas) · `tests/test_verificador_actos.py`
        (34) · `tests/test_politica_certificacion_compuesta.py` (33) ·
        JUnit r14 (fa321a02…), wheel 8cda5efa…, sdist 1c65f132….
RIESGO RESIDUAL: (a) el canal es administrativo mientras no se aplique el
        mecanismo de §5; (b) la revocación depende de esa misma fuente;
        (c) el registro sigue en PROPUESTA y por tanto no acredita nada;
        (d) SSE/HTTP sigue siendo el único NOT_RUN de la superficie
        distribuida; (e) **el gate `noop`/`vault_graph` puede ponerse rojo
        por estado del sandbox (ejemplo idempotente sin declarar): hallazgo
        ABIERTO con su siguiente acción definida, no declarado como verde.**
ESTADO DEL DICTAMEN: los seis hallazgos y la revocación quedan respondidos
        en la propuesta; se solicita dictamen sobre este HEAD, declarando
        expresamente el rojo de la CI (24/25) y su clasificación.

LIBERABLE: false — RELEASE_BLOCKED
```

## DECISIONES LISTAS PARA RATIFICACIÓN DEL PROPIETARIO

Ninguna de estas actas está firmada ni se ha generado en nombre del
propietario. Están listas para que él decida, con lo que cada una habilita y
lo que NO habilita.

### DEC-02 — Arquitectura (QG-00/QG-01)

- **Qué se pide:** ratificar la alternativa **B** (migración compatible por
  etapas) con **I2-a** (publicar la superficie de mantenimiento en la wheel) y
  **COST-a** (superficie ligera de baseline), latencia objetivo **≤ 5 s por
  audit**, ventana de deprecación de **una versión**, pruebas **I1–I5**,
  criterio de éxito **5→3 cruces** y **10→0 divergencias** sin tocar el
  snapshot ni ampliar la baseline, y rollback por commit.
- **Qué habilita:** implementar el puerto y las superficies (commits pequeños
  y reversibles), medir I1–I5 y el coste real, y re-certificar un **SHA de
  producto NUEVO** (suite, 26 puertas, E2E desde wheel, CI 25/25, recibos, QA).
- **Qué NO habilita:** tocar el producto congelado `015b776`; re-tomar el
  snapshot; cambiar la política QG-02 (eso es DEC-03); mover datos (DEC-04).
- **Consecuencia si no se firma:** QG-00/QG-01 siguen BLOCKED y el release
  sigue sin poder certificarse.

### DEC-03 — Certificación QG-02 (opción C)

- **Qué se pide:** ratificar la opción **C compuesta** y, con ella, el
  **registro de autoridades** (pasar `estado` a `RATIFICADO` con su acta) y
  **el canal** por el que se publican los actos; decidir si se adopta el
  mecanismo de segregación de §5 (canal protegido, identidad verificable,
  reglas de custodia).
- **Qué habilita:** aplicar el diff propuesto (catálogo, política, colector y
  tests) y reemitir los recibos QG-02 con el veredicto compuesto.
- **Qué NO habilita:** ratificar el residuo AP-36 (eso es DEC-04), excepcionar
  violaciones ni activar la política de producción por declaración.
- **Consecuencia si no se firma:** QG-02 sigue BLOCKED; el registro sigue en
  PROPUESTA y no acredita nada.

### DEC-04 — Residuo `vault-backups`

- **Qué se pide:** (1) **designar custodio** (id + identidad + canal) y
  declararlo en el registro; (2) autorizar, si se quiere, el **archivo de
  preservación no destructivo** verificado contra los hashes del apéndice A.
- **Qué habilita:** la custodia formal del residuo y, con su acto propio, el
  archivo verificado (sin tocar el original).
- **Qué NO habilita:** **trasladar ni purgar** (exigen actos POSTERIORES e
  independientes, con destino y plan de recuperación); ni cuenta como
  certificación por la mera desaparición de la carpeta (la re-auditoría debe
  acreditar las postcondiciones).
- **Estado actual de los datos:** 66 ficheros / 854.108 B, **intactos**
  (3/3 hashes), sin archivar, trasladar, comprimir ni purgar.

### DEC-01, DEC-05, DEC-06

- **DEC-01 (Constitución):** DRAFT — ratificar, enmendar o mantener.
- **DEC-05 (historia publicada):** en espera — conservar con riesgo
  documentado o autorizar un procedimiento de saneamiento.
- **DEC-06 (release):** solo tras todos los QG efectivos y dictamen QA
  favorable. **No se infiere de preferencias ni de dictámenes.**

---

# Respuesta del ejecutor a QA — R19 (autoridad endurecida: registro ratificado, contrato de acta y custodia, e identidad única)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `2369be8` (rama `qa/review-release-cli-mcp-b4f7302-20261027`) — `QA_R18=ACCEPTED_AS_DESIGN_PROGRESS`; `QA-R18-AUTH-01/02/03=P1_OPEN_PRE_ACTIVATION`; `QA-R18-AUTH-04=P2_OPEN_PRE_ACTIVATION`
- **SHA inicial:** `b4f7302632281c56d9f86942fbe0b81ca619ee77` · **Producto congelado (sin modificaciones):** `015b7765b80cac21c6dcf859ae075d036cd01def` (tree `d190fd24…`)

```text
GOAL: RELEASE CLI + MCP PARA TERCEROS

ESTADO: BLOCKED_OWNER_DECISION — los cuatro defectos preactivacion
        (AUTH-01..04) están cerrados en la PROPUESTA con pruebas negativas
        de commits reales. El producto congelado no se ha tocado. El
        mecanismo queda LISTO PARA RATIFICACIÓN, no ratificado. GOAL ABIERTO.
RAMA: work/release-cli-mcp-20261025
HEAD INICIAL: b4f7302
HEAD FINAL: 515f19646730e459a09f8fe45dbfd95946283b25 (+ este delta documental)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def (SIN MODIFICACIONES)
PRODUCT_TREE: d190fd243567556e824795154b6fd44bd76309d5

CORRECCIONES (R19) — cuatro defectos, cuatro causas:
 AUTH-01 — CAUSA: `verificador_desde_registro()` admitia un registro cuyo
   `estado` era PROPUESTA: la presencia de autoridades se confundia con
   puesta en vigor. CORRECCION: se separa CONFIGURACION CARGADA de
   CONFIGURACION EN VIGOR. `registro_en_vigor()` exige `estado: RATIFICADO`
   y un acto de ratificacion propio (existente, alcanzable por el canal
   declarado, con intencion expresa `ACCION: RATIFICAR` + `ESTADO:
   RATIFICADO` + `OBJETO`/`VERSION` del registro, y firmado por la identidad
   declarada). DRAFT/PROPUESTA/PENDING/desconocidos se rechazan; el
   registro NO puede autoactivarse (su ratificacion es un acto externo
   comprobable) y el evaluador bloquea tambien si el verificador no sabe
   decir si el registro esta en vigor. COMMIT: el de esta ronda.
 AUTH-02 — CAUSA: `_autoridad_de()` preferia `autoridad` y el esquema solo
   exigia `firmante` no vacio: un firmante libre con una autoridad
   registrada distinta pasaba. CORRECCION: identificador UNICO de
   autoridad (`autoridad` canonico, `firmante` alias). Si aparecen ambos,
   tienen que resolver a la MISMA autoridad registrada (el esquema rechaza
   la discrepancia y el verificador rechaza alias desconocidos o
   contradictorios). La identidad declarada tiene que coincidir con la del
   commit (`IDENTIDAD_INCOMPATIBLE_CON_EL_CANAL`).
 AUTH-03 — CAUSA: el texto del commit ratificaba por resemblance (contener
   el id de la decision y los tokens del residuo). CORRECCION: CONTRATO DE
   ACTA explicito — ACTO: RATIFICACION, ACCION: RATIFICAR, ESTADO:
   RATIFICADO, DECISION, AUTORIDAD, ALCANCE, RESIDUO, NORMA, RUTA, HUELLA,
   FECHA, CANAL — con distincion inequivoca entre PROPUESTO, CONSULTADO,
   RATIFICADO, RECHAZADO y REVOCADO. Un documento consultivo que mencione
   todos los datos pero no ratifique expresamente devuelve BLOCKED.
 AUTH-04 — CAUSA: la custodia se comprobaba con menossemantica que el acto
   (commit distinto, canal, id y huella). CORRECCION: CONTRATO DE ACTA DE
   CUSTODIA propio — custodio admitido, autoridad, id del acto, id del
   residuo, norma, ruta, huella, operaciones autorizadas, vigencia temporal,
   canal y commit — y una custodia NO autoriza archivar, trasladar ni purgar
   (exigen actos independientes de DEC-04).

PRUEBAS NEGATIVAS Y POSITIVAS: 57/57 en la propuesta (32 de esquema y
        coherencia + 25 de autoridad con OBJETOS GIT REALES en repositorio
        descartable): registro PROPUESTA/DRAFT/PENDING/desconocido, sin acto,
        autoactivado, ratificado por otro, acta consultiva, estados
        PROPUESTO/CONSULTADO/RECHAZADO/REVOCADO, alias contradictorio,
        autoridad desconocida, identidad incompatible, custodia sin
        custodio, custodio no admitido, custodia sin norma/ruta/huella,
        custodia expirada, custodia con operaciones destructivas, SHA
        inexistente, commit ajeno, custodia autoafirmada y verificador sin
        comprobacion de vigencia. Positivo: acto + custodia con contrato
        completo -> PASS con el residuo LISTADO. Los fixtures sinteticos se
        conservan SOLO para el esquema y se declaran como tales.

VERIFICACION EFICIENTE (sin repetir la suite del producto congelado):
        57/57 (propuesta) · 35/35 (manifiesto, copia, politica QG, guard del
        protocolo) · saneamiento exit 0 · doc_counts exit 0 · 26/26 puertas
        (verificacion de las afectadas). El producto congelado NO se ha
        tocado: no procede re-certificacion integral hasta que exista un
        SHA de producto nuevo y autorizado.

CI POR SHA (sin sustituir evidencia entre SHAs):
  40442954197 | 015b776 (producto)    | completed/success | 25/25
  40456389815 | 55ad340 (fix R16)     | completed/success | 25/25
  40464661392 | 09e849c (delta doc.) | completed/failure | 24/25 (carrera de
               | copia del sandbox, corregida en R17)
  40467869545 | 5970dfb (fix R17)     | completed/success | 25/25
  40472633327 | 2054e8d (HEAD doc.)  | completed/success | 25/25
  40474701480 | 2f7b155 (HEAD R18)    | completed/success | 25/25
  40481751486 | b4f7302 (delta R18)   | completed/success | 25/25
  40488879515 | 515f196 (HEAD R19)    | completed/success | 25/25
               | (12 validate + 12 product gates + lint; sin fallidos,
               | cancelados ni omitidos)
SUITE:   r14 vigente para el producto (6334/13/0, 6347 collectados)
PUERTAS: 26/26 (r14, vigente)
E2E:     27/27 (r14, vigente)
WHEEL:   8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
SDIST:   1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656

ESTADO DEL REGISTRO DE AUTORIDADES: PROPUESTA, SIN VIGOR. Con el estado
        actual, `verificador_desde_registro()` devuelve None y el veredicto
        compuesto es BLOCKED: un registro propuesto nunca acredita un PASS.
        Lo que falta para que entre en vigor es un ACTO DEL PROPIETARIO con
        `ACCION: RATIFICAR`, `ESTADO: RATIFICADO`, `OBJETO:
        autoridades-de-decision-v1`, `VERSION: 1`, `FECHA`, firmado por la
        identidad declarada, alcanzable desde el canal declarado.
FUENTE Y CANAL PROPUESTOS: registro `audits/fase2/autoridades-de-decision.yaml`
        (fuente: git + registro), autoridad `propietario-datos` con canal
        `refs/(remotes/origin|heads)/proposal/dec-02b-dec-03c-dec-04pending-20261026`
        (la rama consultiva ya usada por el propietario, commit cc05eab);
        `qa-arquitectonico` SIN canales (dictaminar no es ratificar). El
        ejecutor no puede ampliar el canal de una autoridad por su cuenta.
LIMITACIONES DE IDENTIDAD COMPARTIDA: ejecutor y propietario comparten
        identidad git y permisos de push: el canal es un control
        ADMINISTRATIVO, no criptografico. El verificador acredita que existe
        un acto verificable en la fuente declarada; que emane del propietario
        depende de la integridad del canal — de ahi que DEC-04 exija designar
        custodio y decidir sobre custodia y permisos del canal.

ESTADO DE LOS QG: QG-00 BLOCKED (DEC-02) · QG-01 BLOCKED (DEC-02) ·
        QG-02 BLOCKED (DEC-03 + DEC-04) · QG-03 PASS · QG-04 PASS ·
        QG-05 PASS · QG-06 PASS · QG-07 BLOCKED por prerrequisitos (no por
        una CI fallida). La politica de produccion NO se ha tocado:
        `catalogo-qg.yaml` y `politica_qg.py` intactos.

DEC-01: EN ESPERA (Constitucion DRAFT; sin cambio unilateral)
DEC-02: PROPUESTA — B con I2-a + COST-a, latencia <= 5 s/audit, compat una
        version, invariantes I1-I5, criterio 5->3 cruces y 10->0
        divergencias sin tocar snapshot ni baseline, rollback por commit.
        NO implementada (requiere DEC-02 expresa).
DEC-03: PROPUESTA — C compuesta, sujeta al verificador de autoridad
        corregido (AUTH-01..04 cerrados), a un canal RATIFICADO y a la
        separacion real de decisiones. NO aplicada a produccion.
DEC-04: PENDING — designacion de custodio y opcion de archivo no destructivo;
        traslado y purga son decisiones POSTERIORES e independientes. Los 66
        ficheros siguen intactos (854.108 B, inmutables 3/3 hashes) y NO se
        archivan, trasladan ni purgan.
DEC-05: EN ESPERA (historia publicada; sin cambio unilateral)
DEC-06: SOLO tras todos los QG efectivos y dictamen QA favorable

EVIDENCIAS Y ENLACES: `audits/fase2/verificador_actos.py` (verificador) ·
        `audits/fase2/autoridades-de-decision.yaml` (registro, PROPUESTA) ·
        `audits/fase2/politica_certificacion_compuesta.py` (contrato) ·
        `tests/test_verificador_actos.py` (25) y
        `tests/test_politica_certificacion_compuesta.py` (32) ·
        `audits/fase2/QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md` §6 (contratos) ·
        `audits/handoff/DECISIONES-PROPIETARIO.md` (fichas) ·
        JUnit r14 (fa321a02…), wheel 8cda5efa…, sdist 1c65f132… ·
        hashes de vault-backups en el apendice A del dosier.

SOLICITUD QA: dictamen sobre el nuevo HEAD (propuesta con AUTH-01..04
        cerrados y 57 pruebas de la propuesta). El producto 015b776 y sus
        recibos siguen vigentes: no se ha tocado codigo de producto.

LIBERABLE: false — RELEASE_BLOCKED
```

---

# Respuesta del ejecutor a QA — R18 (autoridad de los actos separada del esquema, manifiesto reconciliado y expedientes listos para firma)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `8be11d3` (rama `qa/review-release-cli-mcp-2054e8d-20261027`)
- **SHA inicial:** `2054e8daa2a4d903c8d30bee84acba32a44e1780` · **Producto congelado (sin cambios):** `015b7765b80cac21c6dcf859ae075d036cd01def` (tree `d190fd24…`)

```text
GOAL: RELEASE CLI + MCP PARA TERCEROS

ESTADO: BLOCKED_OWNER_DECISION — el P1 del dictamen (la ratificación era una
        autoafirmación) está corregido en la PROPUESTA con una fuente de
        autoridad real; el DOC-01 (encabezado histórico) está reconciliado;
        los tres expedientes de decisión están listos para firma. El producto
        congelado NO se ha tocado. GOAL ABIERTO.
RAMA: work/release-cli-mcp-20261025
HEAD INICIAL: 2054e8d
HEAD FINAL: el commit de esta ronda (+ delta documental con la CI del HEAD)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def (SIN cambios)
PRODUCT_TREE: d190fd243567556e824795154b6fd44bd76309d5

CORRECCIONES REALIZADAS (R18):
 1. QA-R17-QG02-01 (P1) — AUTORIDAD separada del ESQUEMA. Antes bastaba un
    `referencia` de 40 hex, un `firmante` cualquiera y
    `custodia.verificada: true` del mismo recibo. Ahora:
      · FUENTE CONFIABLE: `audits/fase2/verificador_actos.py` +
        `audits/fase2/autoridades-de-decision.yaml` (PROPUESTA, sin vigor).
        Un residuo solo se acepta si su decision se verifica contra esa
        fuente: la autoridad consta en el REGISTRO con canal declarado; el
        ACTO existe como commit, es alcanzable desde ese canal y su
        contenido nombra la decision y el residuo (id, norma, ruta y
        huella); no esta revocado; la CUSTODIA es OTRO acto, existente,
        alcanzable y con contenido propio.
      · SIN FUENTE CONFIABLE -> BLOCKED (no PASS). El booleano
        `verificada: true` ya no concede nada por si solo.
      · `firmante` pasa a ser un IDENTIFICADOR DE AUTORIDAD registrada: un
        nombre libre no es autoridad.
      · LIMIT DECLARADO: ejecutor y propietario comparten identidad git y
        permisos de push, asi que el canal es un control ADMINISTRATIVO, no
        criptografico — lo decide y lo vigila el propietario (DEC-03).
 2. QA-R17-DOC-01 (P2) — encabezado del manifiesto y docstring del test
    unificados: el contrato vigente es ASCENDENCIA (el product_sha es
    ancestro del HEAD documental), no `HEAD^`; `doc_parent_sha` queda como
    commit de PUBLICACION INICIAL (e0fc775). Sin tocar hashes ni el SHA
    congelado.
 3. Expedientes DEC-02/03/04 ampliados al contrato de 12 campos (proposito,
    situacion, problema, evidencia, alternativas, riesgos, impacto,
    recomendacion, alcance exacto de autorizacion, operaciones permitidas,
    rollback y QGs afectados).

PRUEBAS FOCALIZADAS: 44/44 (27 de esquema y coherencia + 17 de autoridad con
        objetos git REALES en repositorio descartable) · 8/8 manifiesto ·
        5/5 copia · 97/97 en los ficheros de test tocados (L2) · saneamiento
        exit 0 · doc_counts exit 0. Los fixtures sinteticos se conservan
        SOLO para el esquema y se declaran como tales: no acreditan ninguna
        ratificacion real.

CI POR SHA (sin sustituir evidencia de un SHA por otro):
  40442954197 | 015b776 (producto)    | completed/success | 25/25
  40456389815 | 55ad340 (fix R16)     | completed/success | 25/25
  40464661392 | 09e849c (delta doc.) | completed/failure | 24/25 (carrera de
               | copia del sandbox, corregida en R17)
  40467869545 | 5970dfb (fix R17)     | completed/success | 25/25
  40472633327 | 2054e8d (HEAD doc.)  | completed/success | 25/25
  40474701480 | 2f7b155 (HEAD R18)    | completed/success | 25/25
               | (12 validate + 12 product gates + lint; sin fallidos,
               | cancelados ni omitidos)
SUITE:   r14 vigente para el producto (6334/13/0, 6347 collectados);
         collectables actuales: +17 (autoridad) y los de R17
PUERTAS: 26/26 (r14, vigente — el producto no cambia)
E2E:     27/27 (r14, vigente)
WHEEL:   8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
SDIST:   1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656

ESTADO DE AUTORIDAD DE DEC-03: PENDIENTE. La PROPUESTA ya exige una
        fuente de autoridad comprobable y BLOCKED sin ella; el REGISTRO de
        autoridades versionado esta en estado PROPUESTA (sin vigor) y el
        producto NO ha adoptado ninguna politica: `catalogo-qg.yaml` y
        `politica_qg.py` intactos.

DEC-02: PREFERENCIA B (cc05eab), CONDICIONADA y SIN RATIFICAR. Expediente
        listo: I2-a + COST-a, umbral <= 5 s/audit, deprecacion una version,
        criterio 5->3 cruces y 10->0 divergencias sin tocar snapshot ni
        baseline, pruebas I1-I5 y rollback por commit. NO implementada.
DEC-03: PREFERENCIA C, CONDICIONADA y SIN RATIFICAR. Propuesta con 44 tests
        fail-closed (esquema + coherencia + autoridad); diff propuesto para
        catalogo/politica/colector PREPARADO y NO APLICADO.
DEC-04: PENDING. Actos separados (preservacion / custodia / archivo /
        traslado-purga), cada uno con su autorizacion. Runbook de 9 fases
        parado en la fase 3; 66 ficheros / 854.108 B, inmutables (3/3
        hashes); NINGUNA operacion sobre los datos.
DEC-01/05/06: ABIERTAS, sin ratificacion inferida.

QG-00: BLOCKED — reconciliador exit=1 (10 divergencias; expediente de firma
       inerte). DEC-02.
QG-01: BLOCKED — mismo expediente; baseline 5/5 intacta. DEC-02.
QG-02: BLOCKED — INC-0001 externa (inmutable 3/3); contrato C propuesto con
       44 tests; DEC-03 + DEC-04.
QG-03: PASS (recibos R14 del producto).
QG-04: PASS (recibos R14).
QG-05: PASS (recibos R14).
QG-06: PASS (recibos R14).
QG-07: CI 25/25 del producto y de los fixes; BLOCKED por prerrequisitos
       QG-00/02 (fail-closed), NO por una CI fallida.

NUEVO DICTAMEN QA PENDIENTE: si (8be11d3) queda respondido con esta ronda,
       se solicita dictamen sobre el estado R18 (propuesta DEC-03 con
       verificacion de autoridad y custodia, manifiesto reconciliado).

DECISIONES EXACTAS QUE REQUIERE EL PROPIETARIO:
 1. DEC-02: ¿ratifica B con I2-a + COST-a, umbral <= 5 s, deprecacion una
    version, criterio 5->3 / 10->0, I1-I5 y rollback por commit? (o la
    alternativa que elija, con riesgos expresos).
 2. DEC-03: ¿ratifica la opcion C compuesta, el diff propuesto y el REGISTRO
    de autoridades con su CANAL? (dictaminar no es ratificar: QA no firma
    decisiones del propietario).
 3. DEC-04: ¿que acto se autoriza (preservacion / custodia / archivo /
    traslado-purga), quien es el custodio y cual es el canal de sus actos?
 4. DEC-01 (Constitucion DRAFT), DEC-05 (historia) y DEC-06 (release, solo
    tras QG efectivos y QA favorable).

SIGUIENTE BLOQUE EJECUTABLE TRAS AUTORIZACION: implementar B en commits
        pequenos y reversibles, medir I1-I5 y el coste real, aplicar C con sus
        condiciones, actuar segun DEC-04, congelar SHA NUEVO de producto,
        repetir suite + 26 puertas + E2E desde wheel + CI multiplataforma +
        recibos por subcheck, y pedir QA. Sin esas firmas: espera controlada,
        sin cambios de codigo de producto.

ACCIONES PROHIBIDAS POR FALTA DE AUTORIZACION (no ejecutadas): ratificar
        `ratificado: true`; re-tomar el snapshot; implementar B; modificar
        catalogo-qg.yaml o politica_qg.py; tocar/mover/archivar/purgar
        vault-backups; crear tag o release; fusionar PR o tocar main;
        reescribir historia; declarar el release autorizado.

LIBERABLE: false — RELEASE_BLOCKED
```

---

# Respuesta del ejecutor a QA — R17 (propuestas cerradas fail-closed, manifiesto reconciliado y carrera de copia corregida)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `7d2679a` (rama `qa/review-release-cli-mcp-09e849c-20261027`)
- **SHA inicial:** `09e849cde3aa1bcb4d5d79743fad5ac2ce9a1c17` · **Producto (sin cambios):** `015b7765b80cac21c6dcf859ae075d036cd01def`

```text
GOAL: RELEASE CLI + MCP PARA TERCEROS

ESTADO: BLOCKED_OWNER_DECISION — los dos defectos de la propuesta (P1 y P2)
        corregidos y probados; el manifiesto reconciliado; una regresion de
        CI del HEAD documental ALSO corregida en causa. Lo que queda son las
        decisiones del propietario y el dictamen QA. GOAL ABIERTO.
RAMA: work/release-cli-mcp-20261025
HEAD INICIAL: 09e849c
HEAD FINAL: 5970dfbbb835b0ae4958e2ee8384d343ea52fd27 (+ este delta documental)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def
PRODUCT_TREE: d190fd243567556e824795154b6fd44bd76309d5

REGRESION R15: (cerrada en R16, aceptada por QA 7d2679a) — encoding explicito
CAUSA RAIZ: (R17, nueva) la corrida del HEAD documental 40464661392 fallo en
            UN job (Windows 3.10) con `shutil.Error` al copiar el sandbox
            vivo: el test ignoraba `*.lock` pero NO el directorio `.locks/`,
            que otro worker retira a mitad (WinError 3). Misma clase que
            R13-03b (que ya lo habia corregido en el backup): cada copia
            inventaba su patron.
CORRECCION: UN solo sitio decide el conjunto canonico que se ignora al
            copiar un vault vivo — `sandbox_fixture.copiar_vault` con
            ESTADO_DE_EJECUCION = ('.locks', '*.lock') — y los seis sitios
            que copian un vault vivo lo usan (antes cada uno con un patron
            distinto). El contenido real NO se ignora (test que lo comprueba).
COMMIT: el de esta ronda
REGRESIONES: 5/5 (test_copia_vault_estado) · 35/35 (manifiesto + contrato C)
            · 57/57 (los cinco ficheros de test tocados) · suite r14 y
            puertas 26/26 del producto 015b776, sin invalidar

CI_RUN (por SHA, sin reutilizar):
  40442954197 | 015b776 (producto)    | completed/success | 25/25 success
  40456389815 | 55ad340 (fix R16)     | completed/success | 25/25 success
  40464661392 | 09e849c (delta doc.) | completed/FAILURE | 24/25 — 1 validate
               | en rojo (Windows 3.10) por la carrera de copia de abajo;
               corregida en esta ronda, con su propia regresión
  40467869545 | 5970dfb (HEAD R17)    | completed/success | 25/25 success
               | (12 validate + 12 product gates + lint; sin fallidos,
               | cancelados ni omitidos) — la carrera de copia ya no se
               | reproduce en ninguna columna

SUITE:   r14 vigente para el producto (6334/13/0, 6347 collectados);
         collectables actuales: + 6 (copia) + 18 (contrato C) + 1 (manifiesto)
PUERTAS: 26/26 (r14, vigente — el producto no cambia)
E2E:     27/27 (r14, vigente)
WHEEL:   8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
SDIST:   1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656

QA-R16-QG02-01 (P1) CORREGIDO: la propuesta exigía solo `decision_ref`
        (texto libre) — con DEC-04 «pendiente» la puerta podia dar PASS.
        Ahora una decision de residuo solo vale si es FORMAL: id, estado
        exacto RATIFICADO, firmante, fecha ISO, referencia SHA de 40 hex,
        alcance que COINCIDE con el hallazgo (id, norma, ruta, huella) y
        custodia verificada; y el REGISTRO tiene que apuntar a ese mismo
        hallazgo. PENDING/NOT_GIVEN/vacios/ajenos/ambiguos/registro mal
        formado -> BLOCKED; texto libre -> BLOCKED; escape nuevo -> FAIL.
        El caso positivo usa una decision formal SINTETICA y verificable
        (fixture descartable), no una simulacion de DEC-04 pendiente.
QA-R16-QG02-02 (P2) CORREGIDO: la coherencia de la evidencia es condicion
        previa — conteo ausente/no entero/negativo, array ausente, conteo
        cero con hallazgos, conteo positivo sin detalles, conteo que no
        cuadra, `completo: false`, control no ejecutado y SHA ajeno ->
        BLOCKED (nunca PASS, y una contradiccion no se lee como defecto del
        producto). 27 pruebas en total: 8 de ratificacion, 8 de coherencia,
        3 de clase de veredicto, 2 positivos y las de contexto.

CONTRATO CORREGIDO DEL MANIFIESTO: el manifiesto decia `HEAD^ == product_sha`
        mientras la prueba admitia ascendencia (QA-R16-DOC-01). Unificado:
        el product_sha es ANCESTRO del HEAD documental (`merge-base
        --is-ancestor`), el manifiesto declara `product_ancestor_of_head:
        true` y `doc_parent_sha` = commit que publico el manifiesto por
        primera vez (e0fc775), sin fabricar paternidad inmediata. Se
        preservan product_sha, tree, hashes de artefactos, CI del producto y
        la separacion producto/documentos. Negativo nuevo: un SHA real que
        NO es ancestro (punta de la rama QA) queda rechazado.

QG-00: BLOCKED — reconciliador exit=1 (10 divergencias sin firma);
       expediente de firma inerte (divergencias-aceptadas.yaml)
QG-01: BLOCKED — mismo expediente; baseline 5/5 intacta; propuesta B
       revisada con I2-a/b/c y COST-a/b/c, umbral de latencia y ventana de
       deprecacion PROPUESTOS (PLAN-B §12.3-§12.4)
QG-02: BLOCKED — INC-0001 externa (inmutable 3/3); contrato C con 27 tests
       fail-closed; propuesta de diff sin aplicar (dosier §5)
QG-03: PASS (recibos R14 del producto; el producto no cambia)
QG-04: PASS (recibos R14)
QG-05: PASS (recibos R14)
QG-06: PASS (recibos R14)
QG-07: CI 25/25 del producto (40442954197) y del fix R16 (40456389815);
       BLOCKED por prerrequisitos QG-00/02 (fail-closed)

DEC-01: ABIERTA — Constitucion DRAFT (sin cambio)
DEC-02: PREFERENCIA B (cc05eab), CONDICIONADA y SIN RATIFICAR. Servida para
        firmar: I2-a/b/c y COST-a/b/c con coste/riesgos/pruebas, umbral
        propuesto <= 5 s por audit, ventana de deprecacion de una version,
        criterio de exito (5->3 cruces, 10->0 divergencias, snapshot y
        baseline intactos) y rollback por commit. NO implementada.
DEC-03: PREFERENCIA C, CONDICIONADA y SIN RATIFICAR. El ejecutable ya exige
        decision formal y coherencia de evidencia (27 tests). Diff propuesto
        para catalogo/politica/colector/politica de certificacion PREPARADO y
        NO APLICADO (dosier §5). Con DEC-04 PENDING, la puerta sigue BLOCKED
        aun con la propuesta C.
DEC-04: PENDING — 66 ficheros / 854.108 B, INMUTABLE (3/3 hashes, R15/R16);
        runbook de 9 fases parado en la fase 3; ninguna accion sobre datos.
DEC-05: ABIERTA — historia publicada (sin cambio)
DEC-06: ABIERTA — autorizacion de distribucion, solo tras QG + QA

ACCIONES TECNICAS EJECUTADAS: correccion de la propuesta DEC-03 (P1+P2) con
        sus tests; reconciliacion del contrato del manifiesto (DOC-01) con
        test nuevo; correccion de la carrera de copia del sandbox vivo con
        helper canonico y 6 sitios unificados + 5 tests nuevos; actualizacion
        de expedientes (PLAN-B §12, fichas DEC, dosier QG-02).
ACCIONES PROHIBIDAS POR FALTA DE AUTORIZACION (no ejecutadas): firmar
        `ratificado: true`; re-tomar el snapshot; implementar la migracion B;
        modificar catalogo-qg.yaml o politica_qg.py; tocar/archivar/mover/
        purgar `vault-backups`; crear tag o release; fusionar PR o tocar main;
        reescribir historia; declarar el release autorizado.
EVIDENCIA PRIMARIA Y HASHES: log del job 122057078525 (copia: WinError 3);
        `%TEMP%\opencode\r17-ci-por-sha.json` (estado por SHA);
        `%TEMP%\opencode\r16-ci-resumen.json` (25/25 de 40456389815);
        logs de la ronda R14/R15; JUnit r14 (fa321a02…); wheel 8cda5efa…;
        sdist 1c65f132…; hashes de vault-backups en el apendice A del dosier.
RIESGOS: SSE/HTTP unico NOT_RUN distribuido (declarado); decisiones sin
        firmar; la regresion de copia demuestra que las carreras de locks
        reaparecen si cada sitio improvisa -> centralizado y con test.
BLOQUEOS REALES: DEC-02 (elegir I2 + coste), DEC-03 (firma formal del
        contrato C), DEC-04 (custodia del residuo), DEC-01, DEC-05, DEC-06,
        y el dictamen QA sobre este estado. Todos de decision, ninguno de
        ejecucion tecnica pendiente sin relacion con ellos.
SIGUIENTE ACCION: A) con DEC-02/03/04 firmadas: implementar el alcance
        autorizado en commits reversibles, medir I1-I5 y el coste, re-freeze,
        suite+26 puertas+E2E+recibos+CI del SHA nuevo y pedir QA;
        B) mientras tanto: espera controlada con el release bloqueado.
SOLICITUD QA: dictamen sobre el estado R17 (propuesta DEC-03 fail-closed con
        27 tests, manifiesto reconciliado, carrera de copia corregida) — el
        producto 015b776 y sus recibos siguen vigentes.

LIBERABLE: false — RELEASE_BLOCKED
```

---

# Respuesta del ejecutor a QA — R16 (regresión de codificación corregida, matriz REL al contrato completo y expedientes de firma servidos)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `e47d62f` (rama `qa/review-release-cli-mcp-015b776-20261027`)
- **Registro del propietario tomado en cuenta:** anexo consultivo `cc05eab` (rama `proposal/dec-02b-dec-03c-dec-04pending-20261026`): preferencias DEC-02=B y DEC-03=C **condicionadas y SIN ratificar**; DEC-04=PENDING. No se ha fusionado esa rama ni se ha actuado sobre sus preferencias sin el acto formal.
- **SHA inicial:** `e0fc775` · **Producto (sin cambios):** `015b7765b80cac21c6dcf859ae075d036cd01def` (tree `d190fd24…`)

```text
GOAL: RELEASE CLI + MCP PARA TERCEROS

ESTADO: BLOCKED_OWNER_DECISION — regresion R15 corregida en causa y
        verificada en CI: la corrida del HEAD corregido, 40456389815 sobre
        55ad340, es completed/success con 25/25. Expedientes DEC-01..06
        servidos para firma; el GOAL sigue ABIERTO.
RAMA: work/release-cli-mcp-20261025
HEAD INICIAL: e0fc775
HEAD FINAL: 55ad340918caca237ad18bcc4aec64b05a9333d0 (fix) + este delta
            documental (el HEAD definitivo cuando QA dicte)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def (SIN cambios en R15/R16)
PRODUCT_TREE: d190fd243567556e824795154b6fd44bd76309d5

REGRESION R15: run 40451686234 (e0fc775) — 12 jobs Validate en rojo
CAUSA RAIZ: tests/test_manifiesto_candidato.py (R15) con dos capturas
            subprocess text=True SIN encoding (lineas 63 y 73); el guard de
            portabilidad (test_ningun_sitio_decodifica_con_la_locale) las
            detecto en TODAS las plataformas (12/12 validate; los 13 jobs de
            producto pasaron: el artefacto no se toco)
CORRECCION: encoding="utf-8" explicito en ambas llamadas; sin tocar
            aserciones ni el detector
COMMIT:     55ad340918caca237ad18bcc4aec64b05a9333d0 (fix) + este delta
REGRESIONES: L1 28/28 (manifiesto 7 + portabilidad 21); L2 31/31;
             CI del HEAD: 40456389815 25/25 success

CI_RUN:      40442954197 (producto 015b776): 25/25 success — vigente
CI_SHA:      015b7765b80cac21c6dcf859ae075d036cd01def
CI_JOBS:     25 (12 validate + 12 product gates + lint)
CI_CONCLUSION: success; ademas, la del HEAD corregido 55ad340:
              run 40456389815, completed/success, 25/25 (total_count 25, sin
              fallidos, cancelados ni omitidos) — regresion cerrada en CI

SUITE:   r14 vigente para el producto (6334/13/0); collectables hoy 6363
         (+16 de expediente)
PUERTAS: 26/26 (r14, vigente)
E2E:     27/27 (r14, vigente)
WHEEL:   8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
SDIST:   1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656

QG-00: BLOCKED — reconciliador exit=1 (10 divergencias); identidad/arbol/
       saneamiento OK; EXPEDIENTE DE FIRMA servido (inerte hasta firma)
QG-01: BLOCKED — mismo expediente; baseline 5/5 intacta; propuesta B revisada
       servida (PLAN-B §12: I2-a/b/c y COST-a/b/c con coste/riesgos/pruebas)
QG-02: BLOCKED — INC-0001 externa (inmutabilidad 3/3); contrato C propuesto
       + 9 tests; propuesta de diff para catalogo/politica/colector preparada
       SIN aplicar (QG-02-ESCENARIOS §5); runbook DEC-04 no destructivo §4
QG-03: PASS (recibos R14 del producto; sin cambios de producto)
QG-04: PASS (recibos R14; TD-0008 verificado en la wheel distribuida)
QG-05: PASS (recibos R14)
QG-06: PASS (recibos R14)
QG-07: CI 25/25 del producto; BLOCKED por prerrequisitos QG-00/02 (fail-closed)

REL-00..REL-13: matriz al contrato completo (13 campos por etapa) en el
        informe §10; estados separados TEST_PASS/CI_PASS/QG_PASS/QA_APPROVED/
        OWNER_AUTHORIZED/PUBLISHED
CAPACIDADES DISTRIBUIBLES: SHIPPED_AND_TESTED (CLI producto, MCP stdio,
        runtime, SP-04) · SHIPPED_NOT_TESTED (SSE/HTTP, unico NOT_RUN)
CAPACIDADES FUERA DE ALCANCE: NOT_SHIPPED (python -m cli completa: plan/
        batch/verify-integrity/130; mantenimiento) · DEPRECATED (base64) ·
        OUT_OF_SCOPE (Quick Start checkout)

DEC-01: abierta (Constitucion DRAFT) — ficha lista
DEC-02: PREFERENCIA B del propietario, CONDICIONADA a eleccion I2 (a/b/c) y
        coste (a/b/c): eleccion servida en PLAN-B §12 con coste/riesgos/
        pruebas/plantilla de firma; expediente de firma de las 10
        divergencias inerte hasta `ratificado: true`
DEC-03: PREFERENCIA C, CONDICIONADA: contrato ejecutable + 9 tests + propuesta
        de diff SIN aplicar (§5 del dosier QG-02)
DEC-04: PENDING: runbook no destructivo de 9 fases (§4 dosier); fases 1-3
        hechas (inventario/hashes/inmutabilidad 3/3); sin tocar datos
DEC-05: abierta (historia publicada: conservar con riesgo documentado)
DEC-06: abierta (autorizacion de distribucion, solo tras QG + QA)

EVIDENCIAS: r15-reconciliador-check.* (exit 1, 10 divergencias), log del job
            validate fallido (2 sitios exactos), 28/28 + 31/31 focalizadas,
            inventario vault-backups 3/3 hashes, manifiesto + contrato C en
            el repo con sus tests
RIESGOS: SSE/HTTP unico NOT_RUN distribuido (declarado); DEC sin firmar;
         corrida del HEAD en curso al cierre (CI_PENDING honesto)
BLOQUEOS: ver §QG-00/01/02 y DEC-01..06 — todos de decision del propietario
         salvo el dictamen QA
SIGUIENTE ACCIÓN: con DEC-02 (I2+coste) y DEC-03/04 firmadas: implementar B,
         re-freeze, certificacion integral y CI; sin ellas, espera controlada
SOLICITUD QA: dictamen sobre el estado R16 (producto 015b776 sin cambios +
         derivas corregidas + expedientes servidos)

LIBERABLE: false — RELEASE_BLOCKED
```

---

# Respuesta del ejecutor a QA — R15 (derivas documentales corregidas, contrato C propuesto y expedientes de firma preparados)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `e47d62f` (rama `qa/review-release-cli-mcp-015b776-20261027`) — `QA-R13-06=ACCEPTED_SCOPED`; `CI_MATRIX_25_OF_25=VERIFIED`; `QA-RELEASE=BLOCKED`
- **SHA inicial:** `08f8cef` (HEAD al abrir la ronda)
- **Producto:** **sin cambios en R15** — el candidato sigue siendo `015b7765b80cac21c6dcf859ae075d036cd01def` (CI 25/25, run `40442954197`): todas las correcciones de esta ronda son documentales, de expediente y de prueba

```text
GOAL:       R15 — desbloqueo QG-00/01/02/07 y cierre integral. ABIERTO.
ESTADO:     BLOCKED_OWNER_DECISION — el trabajo tecnico ejecutable sin
            ratificacion esta hecho; lo que queda exige DEC-01..05 y el
            dictamen QA. No hay FALSE PASS: los bloqueos estan a la vista.
RAMA:       work/release-cli-mcp-20261025
SHA INICIAL: 08f8cef
SHA PRODUCTO: 015b7765b80cac21c6dcf859ae075d036cd01def (tree d190fd24)
SHA DOCUMENTACION: el HEAD al dictar (delta de esta ronda; su padre es el producto)

QG-00: BLOCKED — reconciliador --check exit=1 (10 divergencias sin firma);
       identidad/arbol/saneamiento OK; EXPEDIENTE DE FIRMA preparado
       (divergencias-aceptadas.yaml, ratificado:false en las 10; el
       verificador las ignora hasta firma — verificado: sigue exit=1) y
       alternativa equivalente documentada (re-tomar snapshot, preservando
       f049b1bd). Lo desbloquea: DEC-02 (firmar u ordenar el re-take).
QG-01: BLOCKED — mismo expediente; vault_arch verde con baseline 5/5 INTACTA
       (los 5 cruces siguen a la vista, a_eliminar 2027-06-30); plan B §11
       con las enmiendas I2 y coste medidas. Lo desbloquea: DEC-02.
QG-02: BLOCKED — INC-0001 (AP-36 externa, inmutabilidad reverificada 3/3
       hashes). CONTRATO C PROPUESTO y probado:
       politica_certificacion_compuesta.py + 9 tests fail-closed (los 8
       negativos del GOAL + positivo con residuo listado). No toca catalogo
       ni politica. Lo desbloquea: DEC-03 + DEC-04.
QG-03: PASS (recibos R14 del SHA vigentes: la ronda no cambio producto)
QG-04: PASS (recibos R14; TD-0008 ademas verificado EN LA WHEEL distribuida)
QG-05: PASS (recibos R14; paridad CLI/MCP del SHA)
QG-06: PASS (recibos R14; build + contenido 706/706 + instalacion limpia)
QG-07: CI 25/25 del SHA (40442954197); la politica lo deja BLOCKED por el
       prerrequisito QG-00/02 (fail-closed, sin waiver)

DIVERGENCIAS RESUELTAS: 0 resueltas (exigen firma); las 10 caracterizadas
              (8 movimientos legitimos + 2 fichas desactualizadas, causa raiz
              667a6a5) con su expediente de firma listo
CRUCES VIGENTES: 5 (2 pares, a_eliminar 2027-06-30, baseline SIN tocar)
VIOLACIONES: 1 — INC-0001 (AP-36, externa al repo, decision del dueno)
RESPALDOS EXTERNOS: vault-backups reverificado: existe, 66 ficheros /
              854.108 B, INMUTABLE (3/3 hashes clave identicos al dosier R14,
              mtimes de junio), sin mover ni purgar

SUITE:      r14 vigente (6334/13/0, 6347 collectados) + 16 tests nuevos de
            expediente (7 manifiesto + 9 contrato C) = 6363 collectables
PUERTAS:    26/26 (r14; el hook regenera el conteo al commitear)
E2E:        27/27 (r14, vigente)
WHEEL:      8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
SDIST:      1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656
CI:         40442954197 (015b776) 25/25 success · 40448611081 (08f8cef) en
            curso al cierre de esta entrega
RUN ID:     40442954197

PRD:            reconciliado por nota (los objetivos de septiembre se
                preservan; manda MATRIZ-CAPACIDAD-PRODUCTO.md)
ARQUITECTURA:   plan B §11 (I2 medida: el puerto no funciona desde wheel;
                coste medido: ~60x sin enmiendas); expediente de firma DEC-02
CONSTITUCIÓN:   DRAFT (DEC-01)
TD-0008:        RESUELTO — implementacion cc85491 verificada en el repo Y en
                la wheel distribuida; 22 tests + E2E; registro de deuda
                reconciliado (QA-R14-DOC-01); aceptacion QA explicita
                pendiente de dictamen

DECISIONES DEL PROPIETARIO: DEC-01..06 abiertas; expedientes listos para firma
RIESGOS:        SSE/HTTP es el unico NOT_RUN de la superficie distribuida;
                divergencias y AP-36 (decision); el resto en informe §7
EVIDENCIAS:     r15-reconciliador-check.txt (exit 1, 10 divergencias),
                inventario vault-backups (3/3 hashes), 16 tests nuevos,
                manifiesto y contrato C en el repo
COMMITS:        015b776 (producto, R14) + delta documental de esta ronda
BLOQUEOS REALES: DEC-02 (firmar las 10 divergencias u ordenar el re-take del
                snapshot), DEC-03 + DEC-04 (contrato C y residuo), DEC-01,
                DEC-05, DEC-06, y el dictamen QA del estado resultante

LIBERABLE: false
SOLICITUD QA: revisar esta entrega documental sobre el producto 015b776 (los
              recibos R14 siguen vigentes: sin cambios de producto)
```

## 1. Las cuatro derivas del dictamen (`QA-R14-DOC-01..03`, `PORT-01`) — corregidas

1. **TD-0008** (`inventario-deuda.yaml`): entrada con `status: resuelto` y
   bloque `resolution` (commit `cc85491`, 22 tests, E2E, wheel verificada),
   preservando los campos históricos como observación de su SHA de origen
   (`ef77a7b`). DEC-06 e informe §7 actualizados. **Verificado además que la
   wheel distribuida lleva la misma implementación** (`_impl/vault_init.py`).
2. **Manifiesto** (`CANDIDATO-RELEASE.yaml`): rehecho con campos de identidad
   **hex puro** (sin prosa anexada), metadatos en claves separadas
   (`artifact_filename`, `digest`, `evidence_note`, `doc_parent_sha`), la
   convención anti-circularidad documentada, y **7 tests** de validación con
   negativos (hash mal formado, mayúsculas, SHA ajeno, prosa contaminada).
3. **Cabeceras de readiness**: el informe abre con el **estado canónico**
   (product_sha `015b776`, dictamen `e47d62f`, tres plataformas medidas) y el
   corte R12 queda rotulado **HISTÓRICO**; `MATRIZ-CAPACIDAD-PRODUCTO.md` con
   cabecera vigente y fila macOS `CI_PASS`.
4. **PORT-01 — alcance explícito**: verificado contra la wheel que la
   superficie `python -m cli` (`plan`, `batch`, `--verify-integrity`,
   scheduler, salida 130) **no viaja empaquetada**: queda fuera del alcance
   del release (no como deuda del paquete). El único `NOT_RUN` de la
   superficie distribuida es **SSE/HTTP** (`--port` del servidor MCP),
   declarado. PRDs con nota de reconciliación (objetivos preservados; manda
   la matriz). Filas de la matriz de capacidad corregidas.

## 2. QG-00/QG-01: qué lo desbloquea exactamente (DEC-02)

El reconciliador está **fail-closed por diseño**: sus 10 divergencias solo
salen por (a) firma del propietario en `divergencias-aceptadas.yaml`
(mecanismo propio de la herramienta, que exige `ratificado: true` +
`evidencia`) o (b) una orden de re-tomar el snapshot de Archify como revisión
nueva preservando `f049b1bd` — ambas salidas son las que el propio registro
declara (`recomendacion`). **Preparado para firma**: el expediente con las 10
entradas (`ratificado: false`), verificado que hasta la firma el verificador
sigue en exit 1 y la baseline en 5/5. Medición de la ronda: exit `--check`=1,
10 divergencias, `off_port_total=5 = off_port_baseline=5`.

---

# Respuesta del ejecutor a QA — R14 (QA-R13-06 corregido, reconciliación y paquete de decisiones)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-27
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `7dc1a25` (rama `qa/review-release-cli-mcp-e198ffb-20261026`) — `CI_MATRIX_25_OF_25=ACCEPTED`; `QA-R13-06=OPEN_P1`
- **SHA inicial:** `76669e4` (HEAD al abrir la ronda)
- **Candidato de producto:** el commit de congelación de esta ronda (identidad completa en `audits/fase2/CANDIDATO-RELEASE.yaml`)

```text
GOAL:       R14 — cierre de readiness, reconciliacion arquitectonica y release
            controlado: corregir el P1 del dictamen, reconciliar docs,
            preparar las decisiones del propietario y consolidar la matriz
            formal de liberacion. ABIERTO hasta certificacion y autorizacion.
ESTADO:     AVANCE — P1 corregido y certificado; CI del candidato 25/25;
            recibos del SHA emitidos; pendiente: nuevo dictamen QA y
            decisiones del propietario.
RAMA:       work/release-cli-mcp-20261025
SHA INICIAL: 76669e4
SHA FINAL:  015b7765b80cac21c6dcf859ae075d036cd01def (candidato de producto)
PRODUCT_SHA: 015b7765b80cac21c6dcf859ae075d036cd01def (tree d190fd24)
DOCUMENTATION_SHA: el HEAD documental cuando QA dicte (el commit que fija el
            manifiesto definitivo; su padre es el product_sha)

CI:         para e198ffb: corrida 40430269201, 25/25, ACCEPTED por QA.
            para el candidato de esta ronda: corrida 40442954197 (015b776),
            completed/success, 25/25 — la matriz completa del candidato nuevo
MATRIZ:     12 Validate Vault Spec + 12 Product gates (wheel) + Lint
RESULTADO:  25/25 jobs success en AMBAS corridas (40430269201 y 40442954197)

SUITE:      r14 — 6334 passed / 13 skipped / 0 failed (6347 collectados)
PUERTAS:    26/26 (conteos re-medido tras el fix; conteo de tests 6347)
E2E:        27/27 sobre la wheel del arbol del candidato
WHEEL:      8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd
            (equivalencia de contenido 706/706, 0 distintos vs el dist local)
SDIST:      1c65f132434809c22cb5794a4896a4717c542b3dbbf00b15a7c590348fdb7656

QG-00: BLOCKED (recibo: reconciliador exit=1 por divergencias sin ratificar)
QG-01: BLOCKED (mismo bloqueo; vault_arch verde 5/5 baseline)
QG-02: BLOCKED (recibo: total_violations=1, la externa AP-36)
QG-03: PASS (recibo: JUnit r14 + E2E del SHA)
QG-04: PASS (recibo: saneamiento, pip-audit, contencion, destructivas)
QG-05: PASS (recibo: paridad CLI/MCP + AP-40)
QG-06: PASS (recibo: build + instalacion limpia + contenido)
QG-07: CI 25/25 del SHA (40442954197); BLOCKED en politica por QG-00

DIVERGENCIAS: 10 (DIV-01..10), identidad y coste en PLAN-B §11; sin ratificar
AP-36: 1 hallazgo externo (vault-backups), ficha completa con inventario y
       hashes en QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md; sin tocar
CONSTITUCIÓN: DRAFT (DEC-01)

CORRECCIONES: QA-R13-06 (P1): el cuerpo del POST se consumia DOS veces y el
              404 de ruta desconocida podia retener al worker para siempre;
              sin techo de bytes ni plazo en los rechazos
COMMITS:      el commit de congelacion de esta ronda + delta documental
PRUEBAS FOCALIZADAS: L1 token service 20/20; L2 contrato/superficie 121/121
REGRESIONES: 4 tests nuevos HTTP crudos con plazos reales (los 5 criterios
             del dictamen: 404 pronto, 401/403 estables, techo de cuerpo,
             GET/cuerpo incompleto sin retener, SP-04 intacto)
EVIDENCIAS: JUnit r14, 26 puertas, E2E, dist del arbol, recibos por emitir
RECIBOS:    R13 en audits/fase2/RECIBOS-R13-MANIFIESTO.md; R14 tras el
            colector (delta documental)

ACCIONES NEGATIVAS: NEG-03 aplicado (CI_PENDING no reutilizado); NEG-08
              aplicado (el run de e198ffb no acredita al candidato nuevo:
              se consiguio corrida propia); conteos roja por cifra desfasada
              -> re-medida (NEG-01 menor)
CAUSAS RAIZ: doble consumo del cuerpo (orden _payload/drenaje); cifra de
              tests publicada anterior a la ronda
ACCIONES CORRECTIVAS: ver corrective_action en la seccion 1 de esta ronda
RIESGOS ABIERTOS: TD-0008 (P1, propietario), capacidades PRD sin E2E,
              divergencias y AP-36 (decisiones), 5.2/§7 del informe
DECISIONES DEL PROPIETARIO: DEC-01..06 en DECISIONES-PROPIETARIO.md, vacias

LIBERABLE: false
SOLICITUD QA: nuevo dictamen sobre el candidato 015b776 — CI 25/25 concluida
              (40442954197) y recibos emitidos (PROTOCOLO-QA.md §5)
```

## 1. QA-R13-06 corregido (P1 del dictamen `7dc1a25`)

```yaml
corrective_action:
  id: "R14-01"
  incident_id: "QA-R13-06"
  goal_id: "R14"
  source_sha: "e198ffb (donde el dictamen detectó el defecto)"
  observed_result: "POST autenticado a ruta desconocida con JSON: el worker
    quedaba bloqueado tras _payload() re-drenando el cuerpo ya consumido; el
    404 no salía. Los rechazos 401/403 leían sin techo de tiempo; un cuerpo
    mayor a 1 MiB dejaba bytes sin leer (RST posible)."
  expected_result: "404 pronto; rechazos acotados; cuerpos grandes con
    política de cierre declarada; SP-04 intacto."
  root_cause: "el drenaje R13-05 se aplicó como una llamada adicional en el
    camino del 404 (doble lectura) y sin presupuesto de bytes/tiempo."
  affected_resources: ["scripts/vault_token_service.py"]
  affected_contracts: ["servicio de tokens HTTP (SP-04, envelope de ruta)"]
  affected_gates: ["QG-03 (suite), QG-04 (seguridad), QG-06 (wheel), QG-07 (CI)"]
  proposed_fix: "el cuerpo se consume UNA vez al llegar la petición, con techo
    de 1 MiB y plazo de 5 s (_drenar_cuerpo con deadline por chunk);
    _payload decodifica lo ya leído (payload_too_large -> 413); el 404 NO
    re-drena; _autorizado ya no lee bytes."
  implementation_commit: "015b7765b80cac21c6dcf859ae075d036cd01def"
  validation_commands:
    - "python -m pytest tests/test_token_service_seguridad.py -q   # 20/20"
    - "python -m pytest tests/test_produccion_iso.py tests/test_noop_audit.py tests/test_smoke.py tests/test_mcp_sin_servicios_largos.py tests/test_context_memory.py -q   # 121/121"
    - "python -m pytest tests/ -q -n auto   # 6334 passed / 13 skipped / 0 failed"
    - "python scripts/vault_gate.py --strict   # 26/26"
  evidence: ["JUnit r14 (fa321a02…)", "E2E 27/27 (9d6a3c3f…)", "recibos R14: QG-03..06 PASS, QG-00/01/02 fail-closed por decisiones", "CI 40442954197: 25/25 success", "audits/fase2/RECIBOS-R14-MANIFIESTO.md"]
  rollback_strategy: "revertir el commit de congelación: el servicio vuelve al
    drenaje R13-05 (defecto conocido, documentado en el dictamen)"
  owner_decision_required: false
  final_status: "IMPLEMENTADO Y VERIFICADO (CI 25/25 + recibos); el dictamen QA del candidato queda solicitado"
```

Los cuatro tests nuevos ejercitan los cinco criterios de cierre del dictamen:
(1) POST autenticado a ruta desconocida + JSON no vacío → 404 en &lt; 8 s;
(2) 401/403 estables con cuerpo declarado incompleto (el worker no se retiene
más allá del plazo de 5 s); (3) `Content-Length` mayor al techo → 413 sin
bloquear; (4) GET con cuerpo declarado incompleto no retiene; (5) SP-04 sin
cambios — el orden Origin → Host → Bearer es el mismo, solo dejó de leer
bytes.

## 2. Reconciliación arquitectónica y documental (lo que pidió el dictamen)

- **Informe readiness** (`INFORME-READINESS-TERCEROS.md`): §3.3/§3.4/§5.2/§5.3
  reconciliados con la corrida real (macOS ya no es `EXECUTED_FAILED`/«no
  arranca»: la matriz 25/25 está medida en `40430269201` y la decisión §6.3 se
  cierra por evidencia); §7 con el riesgo macOS cerrado y QA-R13-06 añadido
  como corregido; **§10 nueva: matriz formal REL-00..13** con estados medidos.
- **Buzón R13**: bloque desfasado («la CI está en marcha») marcado con su
  **superesión** explícita; el estado vigente vive aquí y en el informe.
- **Plan B** (`PLAN-B-MIGRACION-CRUZES.md` §11 nueva): identidad exacta
  DIV-01..10 (una causa raíz: el movimiento `667a6a5`), **evidencia I2 medida**
  — el puerto propuesto NO funciona fuera del checkout tal como está escrito
  (los dueños AP-40/42/43 son tools `maintenance` con `installed: false`;
  `vault run vault_mcp_catalog --check-params` → exit 3 en la instalación) — y
  **coste medido**: ~149 s frente a ~2,4 s (60×, dominado por AP-42). B queda
  condicionada a las enmiendas I2/coste; DEC-02 lo recoge.
- **QG-02**: ficha completa de `vault-backups` con inventario de solo lectura
  (66 ficheros, ~834 KiB, un snapshot del 2026-06-28, hashes) y las tres
  opciones de certificación con recomendación C (`QG-02-ESCENARIOS-Y-
  VAULT-BACKUPS.md`).
- **Capacidades del PRD sin E2E** (`plan`, `batch`, `--verify-integrity`,
  SSE/HTTP, exit 130): siguen declaradas como **límite no certificado**
  (§5.3.3 del informe); no entran al alcance del canal sin acreditación caso
  por caso.
- **Recibos accesibles**: `RECIBOS-R13-MANIFIESTO.md` (saneado, con estado,
  exit y SHA-256 por subcheck); el de R14 se genera tras el colector.

## 3. Lo que NO se ha hecho (y quién lo tiene)

- Nada del plan B se ejecutó: la decisión DEC-02 (con sus enmiendas) es del
  propietario.
- `vault-backups` no se movió ni purgó: DEC-04.
- La política de QG-02 no se cambió: DEC-03.
- La Constitución sigue DRAFT: DEC-01.
- La historia publicada no se reescribió: DEC-05.
- Sin tag, sin release, sin merge: REL-09+ requieren autorización.

---

# Respuesta del ejecutor a QA — R13 (macOS real, clase de CI y cierre de compatibilidad)

> **SUPERSESIÓN (2026-10-27, ronda R14).** Esta respuesta R13 describe la
> ronda mientras corría: donde dice «la CI del candidato está en marcha» y
> «SHA FINAL: PENDIENTE», el estado vigente es otro — la corrida
> `40430269201` sobre `e198ffb` cerró **25/25 `completed/success`**, el
> dictamen `7dc1a25` la aceptó (`CI_MATRIX_25_OF_25=ACCEPTED`) y abrió el
> hallazgo P1 QA-R13-06, que viaja corregido en la ronda R14. Lo histórico de
> esta sección se conserva tal cual; el estado vigente vive en la sección R14
> (más arriba en este fichero) y en `INFORME-READINESS-TERCEROS.md` §3.

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-26
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `e30e668` (rama `qa/review-release-cli-mcp-408eb23-20261026`)
- **SHA inicial:** `dfc6a06` (HEAD al abrir la ronda)
- **Candidato de producto:** `9c65401` (las correcciones de R13) · el commit
  documental posterior es el que publica este buzón.

```text
GOAL:       Cerrar la compatibilidad multiplataforma: corregir los fallos REALES
            de macOS y de Windows, conseguir la matriz completa y reconciliar la
            documentacion con el estado real de la CI.
RAMA:       work/release-cli-mcp-20261025
SHA INICIAL: dfc6a06
SHA FINAL:  PENDIENTE (el commit que publica este buzon)
ESTADO:     AVANCE — los cuatro fallos de macOS y el de Windows 3.10 están
            corregidos, con su regresion; la CI del candidato esta en marcha.
            NO MERGE. NO RELEASE. NO se declara multiplataforma hasta 25/25.
```

## 0. La corrección de fondo: la CI no estaba bloqueada

La ronda anterior (y este informe) afirmaban que «la CI está bloqueada por
facturación» y que los jobs de macOS «no arrancan». **Era una lectura de un
instante**: los jobs de macOS tardan mucho en recibir runner (en las corridas
intermedias se les vio en `queued` durante horas) y **cuando por fin corren,
fallan**. El estado final de la corrida del candidato `408eb23` es
**21 verdes / 4 rojos / 0 pendientes**, y los 4 rojos son las cuatro columnas
`validate` de macOS.

| Corrida | SHA | Éxitos | Fallos | Pendientes |
|---|---|---:|---:|---:|
| `40340865847` | `408eb23` | 21 | 4 (macOS) | 0 |
| `40349132455` | `dfc6a06` | 20 | 5 (macOS + Windows 3.10) | 0 |
| `40420024458` | `9c65401` | **24** | **1** (Windows 3.10: R13-05) | 0 |

Es un sitio mejor para estar: los fallos de macOS eran de producto y de
harness, y ahora tienen causa, corrección y regresión.

## 1. Los seis defectos de esta ronda, con su ficha

| ID | Plataforma | Síntoma | Causa demostrada | Corrección | Regresión | Evidencia | Estado |
|---|---|---|---|---|---|---|---|
| **R13-01** | macOS 3.9-3.12 | `RuntimeError: el servicio no abrió el puerto` (1 FAIL + 11 ERROR por job); el proceso quedaba **vivo y sin escuchar** y el test no decía nada | **sin causa demostrada** —lo dice el dictamen— y el ejecutor tampoco la presume: medido en local, el servicio arranca en **0,017 s**. Lo que sí se midió: el test elegía un puerto «libre», lo cerraba y se lo pedía al servicio (carrera con 8 workers en paralelo), esperaba 30 s sin reportar nada, y el servicio no publicaba su estado de arranque | el servicio **enlaza antes de publicar** el fichero de puerto (su presencia pasa a ser la señal de «ya escucha») y **publica el puerto enlazado**, no el pedido; registra en stderr los tiempos de arranque (import, rutas, enlace, ficheros), sin token. El test pide **puerto 0** (que lo elija el sistema), espera la señal, y si no llega el error dice **código de salida, si el proceso sigue vivo, el puerto, el fichero de puerto y el stderr acotado**, con el token redactado. El techo sube de 30 s a 120 s: no es una espera (el test sondea cada 100 ms y vuelve en cuanto escucha), es un máximo | `test_el_arranque_que_falla_dice_el_codigo_y_el_stderr` | corrida `40340865847` (log del job 121634881128) | CORREGIDO |
| **R13-02** | macOS 3.9-3.12 | `test_heal_legacy_paso_curar_todas_las_notas_legacy`: `assert 5 == 3` | **la cascada que dispara cada escritura crea ficheros mientras el escáner sigue recorriendo**: `vault_io.atomic_write_text` regenera el `index.md` de la sección y escribe las notas de sistema, y el `rglob` del escáner es **perezoso**. En APFS (macOS) ve esos ficheros y en ext4/NTFS no. **Reproducido en local**: una segunda pasada sobre el mismo vault contaba 6 = 3 + los 3 que la primera creó | el inventario se **materializa antes de curar** (una pasada no puede cambiar su propio inventario) y los artefactos derivados se excluyen por su dueño (`vault_registry.es_artefacto_derivado`). Además el escáner **publica el inventario** (ruta relativa, clase y motivo), que es el dato que faltaba para distinguir un recuento mal de un defecto | `test_heal_legacy_no_cuenta_lo_que_la_pasada_crea`, `test_heal_legacy_publica_el_inventario_exacto` | corrida `40340865847` | CORREGIDO |
| **R13-03a** | macOS 3.11 | el segundo proceso del test de exclusión **moría** con `OSError: [Errno 22] Invalid argument: .../.locks/contador.txt.lock` | en macOS, cuando `.locks/` se retira mientras otra ruta se resuelve, `mkdir` responde **EINVAL/ENOTDIR**; en Linux el mismo caso es ENOENT, que el código ya contemplaba. El proceso debía **esperar su turno**, no morir | EINVAL y ENOTDIR se compiten otra vez, con el **plazo como único freno**: un nombre de verdad inválido sale por timeout, no por un bucle infinito | `test_un_einval_al_crear_el_lock_se_compite_otra_vez` (positiva) y `test_un_einval_permanente_no_espera_sin_fin` (negativa) | corrida `40340865847` (traza del hijo) | CORREGIDO |
| **R13-03b** | Windows 3.10 | `test_backup_base64`: `shutil.Error: ... vault-sandbox/00_System/.locks` — el directorio desaparece mientras se copia | la copia del sandbox **vivo** se coge en mitad: otra prueba en paralelo toma y suelta locks | el estado de bloqueo es de **ejecución**, no de contenido: la copia lo ignora (mismo criterio que usa la auditoría del toolkit) | el mismo test, con la copia coherente | corrida `40349132455` | CORREGIDO |
| **R13-04** | (política) | toda CI que no fuera `success` se etiquetaba `CI_PENDIENTE`, **incluida una que ya había terminado en rojo** | el evaluador solo miraba runs **exitosos**; una CI concluida con jobs rojos salía `no_verificable` y el veredicto decía «pendiente» | tres clases: **`CI_PENDING`** (en cola o en curso), **`CI_FAILED`** (concluida con fallos, con los jobs en rojo nombrados) y **`CI_PASS`** (conclusión `success`). La regla fail-closed no cambia: solo `success` pasa | `test_una_ci_concluida_en_rojo_es_fallida_y_no_pendiente`, `test_una_ci_cancelada_tambien_es_fallida_y_no_pendiente`, `test_una_ci_en_curso_es_pendiente_y_no_fallida`, `test_sin_dato_de_ci_no_hay_pass` (política) y `test_un_run_concluido_en_rojo_se_dice_failure_y_cuales_jobs_fallaron`, `test_un_run_concluido_en_rojo_sin_jobs_sigue_diciendo_failure` (colector) | corrida `40340865847` | CORREGIDO |
| **R13-05** | Windows 3.10 (corrida de verificación `40420024458`: 24/25) | `test_una_peticion_de_navegador_se_rechaza_aun_con_token`: `ConnectionAbortedError: [WinError 10053]` donde el test esperaba **403** | al rechazar una petición que trae cuerpo (`POST /stop` con `Origin` ajeno), el servicio respondía 403 y cerraba la conexión **con el cuerpo sin leer**: el núcleo de TCP responde RST y el cliente lee una conexión abortada, no la respuesta. Carrera clásica del RST contra la lectura (solo 1 de 8 columnas la vio) | el camino de rechazo de SP-04 **drena el cuerpo** (`Content-Length`, acotado a 1 MiB) antes de responder, en los tres rechazos de `_autorizado` y en el 404 de `do_POST` | el propio test, que ahora pide el 403 cinco veces seguidas (16/16 en local) | log del job `121911857070` (corrida `40420024458`) | CORREGIDO |

## 2. Lo que se comprobó de cada corrección

```text
REGRESION FOCALIZADA:  154/154 en los nueve ficheros de test tocados
                        (lock entre procesos, onboard legacy, token service,
                        backup base64, politica QG, colector, audit de normas,
                        AP-07, AP-64).
REPRO LOCALES:         (a) EINVAL de mkdir simulado: la toma sale adelante y un
                            EINVAL permanente sale por plazo;
                        (b) escaner legacy: 1a pasada 3, 2a pasada 5 (antes 6),
                            con el indice derivado excluido por su dueno;
                        (c) servicio de tokens: 16/16 en 5,5 s (antes: 12
                            timeouts de 120 s y 24 min de corrida);
                        (d) copia del sandbox: la carrera de `.locks` desaparece.
CI DE VERIFICACION:    corrida 40420024458 (9c65401): 24 de 25. Las cuatro
                        columnas de macOS pasan por primera vez; el unico
                        rojo (Windows 3.10) destapó el defecto R13-05 del
                        rechazo con cuerpo — corregido y su regresión
                        reforzada. La corrida del commit final de R13 es la
                        que acredita el 25/25.
```

## 3. Certificación del candidato

```text
SUITE:   6330 passed / 13 skipped / 0 failed en 1342,90 s (JUnit r13b,
         6343 collectados). Sin fallos ni errores; misma cifra de tests
         que la corrida r13a (6330) — el drenaje no añade tests, refuerza
         la regresión de R13-05 dentro del test que la ejerce.
PUERTAS: 26/26 en 766,11 s
E2E:     27/27 con la wheel reconstruida desde el codigo del candidato
WHEEL:   3a9f2ddad28d78fcad7ebfc2e4e106960c2b51cee0d7c7092d36ea41b52ef39d
SDIST:   7f20943359fd5d8e4b5d73771f684e332e99a61ec2c4bb94e2f612662bc6b293
CI:      corrida 40430269201 (e198ffb): 25/25 — completed/success, cero
         jobs en rojo; las cuatro columnas de macOS pasan por primera vez.
```

Recibos por subcheck del SHA `e198ffb` (colector R13): QG-03, QG-04, QG-05,
QG-06 y QG-07 **PASS** con artefacto y SHA-256 por subcheck; la QG-07 acredita
el run `40430269201` (`completed/success`, `total_count: 25`, los 25 jobs
nombrados). QG-00 y QG-01 fallan **solo** por el reconciliador (las 10
divergencias sin ratificar — mismas fichas, mismo exit=1 que la R12) y QG-02
**solo** por la violación externa de `vault-backups` (`total_violations=1`,
la externa). La política de los recibos: los mismos BLOCKED de la R12 —
`liberable: false` por `PREREQUISITO_NO_CUMPLIDO:QG-00` — que es el estado
honesto: lo que bloquea el release son las decisiones del propietario, no el
trabajo del ejecutor.

Sobre el hash del paquete: la construccion **no es reproducible** (el ZIP lleva
marcas de tiempo), asi que el sha256 del fichero cambia entre construcciones;
lo que se midio es el CONTENIDO (706 miembros, 0 diferencias: wheel del E2E
`3a9f2dda…` contra la wheel del dist del candidato, medido el 2026-10-27). El
hash de referencia es el de la construccion certificada.

## 4. Decisiones del propietario (siguen abiertas, sin cambios)

1. **Divergencias DIV-01..10** (cinco cruces): alternativa **B** con el plan
   preparado (`audits/architecture/PLAN-B-MIGRACION-CRUZES.md`) y con la
   exigencia del dictamen: la independencia debe ser **semántica y operacional**,
   no solo ausencia de aristas de importación.
2. **Política de QG-02** (doble escenario): propuesta, no ratificada.
3. **`vault-backups`** externo (AP-36): purgar o declarar con dueño y fecha.
4. **Constitución**: sigue DRAFT.
5. **Reescritura de historia**: sigue siendo del propietario.

## 5. Lo que NO se ha hecho

- No se ha modificado `main` (sigue en `1c34754`), ni se ha fusionado PR #1, #2
  ni #3, ni se ha reescrito historia, ni se ha editado el buzón de QA.
- No se ha ampliado ninguna baseline, ni se ha relajado ninguna aserción, ni
  se ha convertido ningún fallo en SKIP.
- No se ha declarado PASS de plataforma: macOS sigue sin acreditar hasta que
  la matriz dé 25/25.
- No se ha ratificado ninguna decisión del propietario.

```text
COMMITS:   9c65401 (fix R13: lock EINVAL, escaner legacy, servicio de tokens,
           clase de CI) + este buzón (delta documental)
EVIDENCIAS: logs de los jobs macOS y de Windows 3.10 de las corridas
           40340865847 y 40349132455 (descargados y analizados); repro local
           del EINVAL simulado; repro local del escaner legacy (3 y 5); servicio
           de tokens arrancando en 0,017 s; JUnit de la suite.
SOLICITUD QA: SÍ — sobre el candidato de esta ronda, con la matriz de 25 jobs y
           los recibos por subcheck del SHA nuevo. Si las decisiones del
           propietario siguen abiertas, el dictamen correcto es BLOCKED con esas
           causas.
```

---

# Respuesta del ejecutor a QA — R12 (remediación de CI, reconciliación documental y certificación)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-26
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `defc657` (rama `qa/review-release-cli-mcp-316623a-20261026`)
- **SHA inicial:** `316623a` (HEAD al abrir la ronda)
- **SHA final:** `408eb23` · **Candidato de producto congelado:** `408eb23`
  (los commits posteriores de esta misma entrega son documentales)

```text
GOAL:       Remediar los fallos reales de CI, verificar compatibilidad,
            reconciliar la documentación de readiness/protocolo/PRD y
            preparar (sin aplicar) la decisión de arquitectura B.
RAMA:       work/release-cli-mcp-20261025
SHA INICIAL: 316623a
SHA FINAL:  408eb23
ESTADO:     AVANCE — los DIEZ defectos reales que la CI destapó están
            corregidos y comprobados (D1-D10); la corrida del SHA final tiene
            17 de 25 jobs en verde, incluidos los 8 validate de Windows y
            Linux; la documentación está reconciliada con su fuente; QG-00/01/02
            siguen BLOCKED por decisiones del propietario y QG-07 por los 8
            jobs macos-latest que no arrancan. NO MERGE. NO RELEASE.
```

## 1. CI — lo que de verdad pasó y lo que se corrigió

```text
CI:
RUN ID:        40340865847 (SHA final 408eb23) · 40335869688 (8b87b24) ·
               40326462714 (0fffbc3) · 40317033977 (9e0bcd7) · 40299732445
               (freeze 36c91e0)
JOBS TOTAL:    25 (12 validate = 3 SO x 4 Python · 12 product-gates · 1 lint)
JOBS PASS:     17  (lint + 8 product-gates + los 8 validate de Windows y Linux)
JOBS FAIL:     0   en la corrida del SHA final
JOBS QUEUED:   8   (los 8 macos-latest: NO arrancan, en 5 corridas seguidas)
JOBS IN_PROGRESS: 0
```

**La hipótesis de la ronda anterior («la CI está bloqueada por facturación») queda
refutada**: la cuenta ejecuta y los jobs de Windows y Ubuntu terminan. El
límite real es otro, y es externo: **los 8 jobs `macos-latest` no arrancan**,
en dos corridas seguidas. Consecuencia: la matriz multiplataforma **no está
completa** y QG-07 no puede cerrarse (su check exige CI con conclusión).

### 1.1 Los tres defectos reales, con su ficha

```text
ID: D1
Job: Validate Vault Spec (ubuntu/windows, 3.9-3.12) — 8 jobs
Sistema operativo: Ubuntu 22.04 / Windows Server 2022
Python: 3.9.13, 3.10.11, 3.11.9, 3.12.10
Test: 18 tests de historia (changelog 3, contrato_nota 6, metricas 4,
      blueprint 4, hf201 1)
Síntoma: «hash inexistente» para commits que SÍ existen en GitHub;
         returncode 128 en git show/cat-file; ValueError al resolver el
         rango 8f24030..6ddf04e; blueprint «difiere de los registros».
Causa comprobada: actions/checkout@v4 hace checkout SUPERFICIAL (--depth=1):
         los objetos históricos no están en el clon. El commit existe en
         GitHub; lo que faltaba era el objeto en el clon.
Hipótesis descartadas: (a) «el commit no existe en GitHub» — QA lo verificó
         contra GitHub y el hash sí está; (b) «el test está mal» — el mismo
         árbol con historia completa pasa; (c) «es de Windows» — falla
         también en Ubuntu.
Cambio correctivo: fetch-depth: 0 SOLO en el job validate (product-gates y
         lint no leen historia y siguen con clon superficial).
Regresión negativa: clon local --depth=1 -> 19 fallos en los cinco ficheros
         afectados (mismo árbol, mismo intérprete).
Regresión positiva: el mismo árbol con historia completa -> 129/129 pasados.
Evidencia: corrida 40299732445 (logs de los 8 jobs), clon local medido.
Estado: CORREGIDO (pendiente la corrida de verificación en CI).
```

```text
ID: D2
Job: Validate Vault Spec (windows-latest, 3.9-3.12) — 4 jobs
Sistema operativo: Windows Server 2022 · Python: 3.9-3.12
Test: tests/test_mcp_runner.py::test_la_tool_por_modulo_se_ejecuta_por_mcp
Síntoma: TOOL_EXECUTION_FAILED con «ModuleNotFoundError: No module named
         'yaml'» en la respuesta JSON-RPC (no en el log del servidor).
Causa comprobada: el servidor elegía `py` como intérprete; en el runner de
         Windows `py` resuelve el Python REGISTRADO en la imagen base (sin
         PyYAML), no el de la matriz, donde `pip install -e ".[dev]"` sí
         instaló la dependencia. En Ubuntu `py` no existe y `python3` sí
         resolvía el intérprete correcto — de ahí que solo rompiera Windows.
Hipótesis descartadas: (a) «falta PyYAML en el producto» — está declarada en
         pyproject.toml y el job la instala; (b) «el runner no la instala» —
         el paso Install dependencies sale bien; (c) «es la wheel» — el fallo
         ocurre también en el checkout.
Cambio correctivo: detectPython() sondea `python3` -> `python` -> `py` (en ese
         orden) y exige a cada candidato `import yaml` (la única dependencia
         declarada); la elección explícita VAULT_MCP_PYTHON no se sondea pero
         se avisa en el arranque si no puede importar la dependencia.
Regresión negativa: antes, `tools/list` + `tools/call` de vault_gobernanza
         devolvían TOOL_EXECUTION_FAILED (medido en la corrida real).
Regresión positiva: 9/9 test_mcp_runner, 8/8 test_mcp_instalado, y medición
         en vivo: el servidor arranca, responde y expone 97 tools.
Evidencia: corrida 40299732445 (log del job) + medición en vivo del servidor.
Estado: CORREGIDO.
```

```text
ID: D3
Job: Validate Vault Spec (windows-latest, 3.9 y 3.10) — 2 jobs
Sistema operativo: Windows Server 2022 · Python: 3.9.13, 3.10.11
Test: tests/test_impl_shadow.py::test_impl_preferred_over_fake_cwd_vault_io y
      tests/test_portabilidad_v4030.py::test_ejecutar_lee_utf8_aunque_el_llamador_pida_texto
Síntoma: el hijo muere en la INICIALIZACIÓN: «Fatal Python error:
         _Py_HashRandomization_Init: failed to get random numbers to
         initialize Python / Python runtime state: preinitialized», stdout vacío.
Causa comprobada: los dos fixtures lanzan al hijo con un env CURADO
         (sustituye el entorno entero) SIN SystemRoot. Sin esa variable, el
         win32_urandom de 3.9/3.10 (CryptGenRandom) no consigue números y el
         hijo muere antes de ejecutar una línea. 3.11+ usa ProcessPrng y
         sobrevive: de ahí que las columnas 3.11 y 3.12 no fallaran.
Hipótesis descartadas: (a) «es un fallo de la suite» — el hijo es un Python
         sano; (b) «es la codificación» — el problema ocurre ANTES de que el
         hijo escriba nada; (c) «es aleatorio» — se reproduce de forma
         determinista en local.
Cambio correctivo: los dos fixtures heredan la invariante del anfitrión
         (SYSTEMROOT) y dejan intacta su curación (PATH, PYTHONIOENCODING).
Regresión negativa: `py -3.9` con env sin SystemRoot -> rc=1 con el stderr
         IDÉNTICO al de la CI.
Regresión positiva: `py -3.9` con SystemRoot -> rc=0; `py -3.12`/`py -3.14`
         sin SystemRoot -> rc=0 (3.11+ usa ProcessPrng).
Evidencia: repro local medido + logs de la corrida 40299732445.
Estado: CORREGIDO.
```

```text
ID: D7
Job: Validate Vault Spec (ubuntu-latest, 3.9-3.12) — 4 jobs
Sistema operativo: Ubuntu 22.04 · Python: 3.9-3.12
Test: puerta `conteos` (vault_doc_counts --check --strict)
Síntoma: 25/26 puertas; failed_gates=["conteos"]. La suite de esos mismos
         jobs estaba VERDE (6302-6306 passed, 0 failed).
Causa comprobada: la puerta compara la cifra de tests publicada con
         `pytest --collect-only -q`, y esa cifra DEPENDIA DEL SISTEMA:
         tests/test_read_ruta_canonica.py solo anadia en Windows las dos
         variantes que usan separador de Windows y caja distinta, asi que la
         columna Linux recogia 6318 y la published era 6320 (medida en
         Windows). Medido en las 4 columnas: 6318+0 (Linux) y 6320 (Windows).
Hipótesis descartadas: (a) «la puerta esta mal medida» — en Windows daba
         26/26 con la misma cifra; (b) «son tests que no se ejecutan» — la
         suite estaba en verde; (c) «es un problema del runner» — las 4
         columnas de Linux fallan igual y las de Windows no.
Cambio correctivo: las cuatro variantes se COLECTAN en todas las plataformas
         y las dos de Windows se saltan fuera de Windows: la cifra queda
         igual en todos los sistemas (6332) y la cobertura de Windows no se
         pierde.
Regresión negativa: con la parametrizacion por sistema, la columna Linux
         recogia 6318 y la puerta fallaba (corrida 40317033977).
Regresión positiva: 6332 collectados en Windows y en POSIX; puerta
         `conteos` en verde; 4/4 en test_read_ruta_canonica.py.
Evidencia: corrida 40317033977 (jobs de ubuntu, logs completos) y la
         comparacion de las listas de tests collectados.
Estado: CORREGIDO (pendiente la corrida de verificacion en CI).
```

```text
ID: D8
Job: Validate Vault Spec (windows-latest, 3.12) — primer job que pasa las
     puertas y falla en el paso siguiente
Sistema operativo: Windows Server 2022 · Python: 3.12.10
Paso: Containment audit (AP-36, strict)
Síntoma: `vault_norms --audit --root vault-sandbox --strict` -> exit 1 con
         13 violaciones (CN-03 x5, AP-07 x4, AP-64 x4) sobre las notas
         semilla del sandbox.
Causa comprobada: el paso de contencion de la CI audita el sandbox que el
         propio job acaba de construir con `tests/sandbox_fixture.py
         --bootstrap`, y la semilla (tests/fixtures/sandbox-seed.json) escribia
         las notas con `status: accepted`, sin las secciones de AP-07 y sin
         `responsable` de AP-64. Eran las MISMAS 13 que arrastraba el ledger
         de QG-02: no era un defecto de la CI, era contenido nuestro, y la
         CI lo veia porque construye el sandbox desde la semilla.
Hipótesis descartadas: (a) «es la auditoria la que va mal» — la misma
         auditoria, con el codigo actual y la semilla corregida, da 0
         violaciones en el sandbox canonico; (b) «es contamination del
         entorno» — las 13 son de las notas semilla, con sus rutas.
Cambio correctivo: la semilla escribe notas canonicas (5178399).
Regresión negativa: corrida 40317033977, paso de contencion en Windows 3.12
         con exit 1 y las 13 violaciones.
Regresión positiva: audit del sandbox canonico con el codigo actual: 1
         violacion (AP-36, externa) y en CI 0; E2E 27/27.
Evidencia: log del job 121552106864 (JSON completo de la auditoria).
Estado: CORREGIDO (pendiente la corrida de verificacion en CI).
```

```text
ID: D9
Job: Validate Vault Spec (windows-latest, 3.9-3.12) — 4 jobs
Sistema operativo: Windows Server 2022 · Python: 3.9-3.12
Paso: "Run vault_norms --list"
Síntoma: el paso fallaba en las cuatro columnas de Windows y PASABA en las
         cuatro de Ubuntu, con el mismo codigo y el mismo repositorio:
         «SyntaxError: '[' was never closed».
Causa comprobada: el paso usa `python -c "..."` con comillas dobles escapadas
         dentro; con el shell por defecto de Windows (PowerShell) las comillas
         se pierden al pasar el argumento al proceso nativo y el codigo llega
         partido. En bash el mismo texto funciona. Reproducido en local: con
         PowerShell 5.1 tampoco vale la forma de comillas simples (PowerShell
         quita las comillas interiores).
Hipótesis descartadas: (a) «es el codigo de las normas» — el mismo comando
         pasa en Ubuntu; (b) «falta un interprete» — el paso anterior (spec
         validate) usa el mismo python y pasa; (c) «es el quoting de YAML» —
         el error es del interprete de python, no del yaml.
Cambio correctivo: el paso declara `shell: bash` (que esta en los tres
         runners y es el shell que ya usan el paso de la wheel y el de SBOM) y
         el codigo de python usa comillas simples, sin escapes.
Regresión negativa: con el shell por defecto, la columna de Windows falla
         (corrida 40326462714, paso "Run vault_norms --list").
Regresión positiva: verificado en el bash de esta maquina ("AP norms
         registered: 76", exit 0) y en CI: windows-3.12 completo en verde
         (corrida 40335869688) con ese paso en success.
Evidencia: logs de los jobs de las corridas 40326462714 y 40335869688.
Estado: CORREGIDO.
```

```text
ID: D10
Job: Validate Vault Spec (windows-latest, 3.11) — 1 job
Sistema operativo: Windows Server 2022 · Python: 3.11.9
Test: tests/test_vault_sdd_init.py::TestSkillExecution::test_skill_idempotency
Síntoma: «README.md not idempotent», con una UNICA diferencia: dos lineas
         «Generated at» con un segundo de distancia (14:25:55.000Z contra
         14:25:54.000Z).
Causa comprobada: los generadores del SDD estampan el instante de la
         escritura («Generated at», «Generado») y el JSON lleva
         `generated_at`; el test generaba dos veces y comparaba byte a byte, de
         modo que el resultado dependia del SEGUNDO en que caian las dos
         generaciones y no del codigo. El repo ya conocia la otra causa del
         mismo fallo —una mutacion concurrente del registro que el SDD cuenta,
         corregida con `dry_run=True` en el runner de contexto, medido el
         2026-10-23—; esta, el reloj, seguia viva.
Hipótesis descartadas: (a) «el generador produce contenido distinto» — con
         el instante normalizado, los doce generadores dan contenido
         identico; (b) «es de Windows» — la comparacion es del generador, no
         de la plataforma; (c) «es contencion del runner» — el test corre en
         su directorio temporal.
Cambio correctivo: la comparacion normaliza SOLO el instante (la etiqueta de
         la linea y el resto del texto se siguen comparando; en el JSON se
         excluye la clave `generated_at`).
Regresión negativa: dos generaciones separadas por 1,2 s (cruce de segundo
         forzado) dan contenido CRUDO distinto en README.md.
Regresión positiva: el mismo par da contenido NORMALIZADO identico en los
         doce generadores; 15/15 tres veces seguidas.
Evidencia: corrida 40335869688 (job de Windows 3.11) y la comprobacion local
         con el cruce de segundo forzado.
Estado: CORREGIDO.
```

### 1.2 Correcciones adicionales de esta ronda

| ID | Dónde | Qué | Comprobación |
|---|---|---|---|
| D4 | `mcp/nodejs/vault-mcp-server.mjs` | `vault://graph` llamaba `jsNativeGraph()` **sin la raíz del vault**: el `catch` devolvía el error dentro del texto del recurso, con apariencia de contenido válido. Ahora pasa `detectVaultRoot()` y el `catch` devuelve JSON con `ok:false` y `error_code` | `tests/test_mcp_recursos.py` (9 casos) leyendo los 7 recursos por sesión JSON-RPC real |
| D5 | `tests/sandbox_fixture.py` | el bootstrap reindexaba ANTES de que las tools escribieran sus notas derivadas: el sandbox quedaba con 3 notas en disco y ninguna indexada (AP-47) — y la puerta de contención de la CI lo mide. Se reindexa otra vez al final | audit del sandbox tras el cambio: 1 violación (la externa) en vez de 14 + AP-47 |
| D6 | `.github/workflows/vault-ci.yml` | la CI corría la suite **secuencial**, mientras la forma canónica del repo es `pytest tests/ -q -n auto` (la dice `pyproject.toml` y el checklist). Se usa la forma canónica y se publica el **JUnit como artefacto**: sin él, un job en curso no tiene log parcial descargable y un fallo llega sin el detalle de qué test falló | mismo conjunto de tests, mismas aserciones; el artefacto `junit-<os>-py<version>` es el recibo de cada columna |

## 2. Certification

```text
SUITE:   6319 passed / 13 skipped / 0 failed en 994,9 s (JUnit r12h, sobre el
         SHA final 408eb23); 6332 collectados, 0 fallos, 0 errores.
PUERTAS: 26/26 en 532,9 s (mismo contenido)
E2E:     27/27 con wheel reconstruida desde el codigo (el guion construye la
         wheel el mismo desde HEAD)
WHEEL:   6389a9cefa599b26ef11f875851e7ca126b2487867b14e753cc93fd43ab0e6ae
SDIST:   8b91c07a0b16af083586ec6ed05dbb24f6210a0a7971f30654038babf5e51151
```

**Sobre el hash del paquete:** la construccion **no es reproducible** (el ZIP
lleva marcas de tiempo), asi que el sha256 del fichero cambia entre
construcciones. Lo que si se midio es el CONTENIDO: la wheel del E2E y la
reconstruida tienen **706 miembros y 0 ficheros con contenido distinto**. El
hash de referencia es el de la construccion certificada.

## 2.1 Lo que la CI mostro de los arreglos (corrida 40317033977, sobre 9e0bcd7)

| Columna | Suite | Puertas | Paso alcanzado |
|---|---|---|---|
| ubuntu 3.9 / 3.10 / 3.11 / 3.12 | **VERDE** (6302-6306 passed, 0 failed; 31-45 min) | 25/26 — falla `conteos` (D7) | contencion (D8) |
| windows 3.12 | **VERDE** (6307 passed, 0 failed) | **26/26** | contencion (D8) |
| windows 3.9-3.11 | en curso al cierre de esta entrega | — | — |
| macos 3.9-3.12 | **no arranca** (8 jobs en cola) | — | — |

Es decir: **los tres defectos de la ronda anterior (D1, D2, D3) están
corregidos y la CI lo demuestra**: en las columnas que llegaron a la suite,
la suite está en verde. Lo que quedaba era elCounts (D7) y el contenido de la
semilla (D8), ambos corregidos en esta misma ronda.

## 3. QG-00 a QG-07 (estado autologous)

**Recibos externos por subcheck** del SHA final `408eb23` (colector con
`--ejecutar`: cada subcheck tiene su verificador, su exit code, su artefacto
propio y su SHA-256; el directorio de recibos vive FUERA del arbol versionado
para que el commit no contenga su propia acreditacion):

| QG | Estado del recibo | Subchecks (estado) | Lo que falla, si falla |
|---|---|---|---|
| QG-00 | **FAIL** (exit 1) | identidad_git=ejecutado · arbol_limpio=ejecutado · saneamiento=ejecutado · **reconciliador_archify=fallido** | las 10 divergencias sin ratificar (decisión del propietario) |
| QG-01 | **FAIL** (exit 1) | vault_arch=ejecutado · **reconciliador_archify=fallido** | las mismas 10 divergencias |
| QG-02 | **FAIL** (exit 1) | puertas_26=ejecutado · auditoria_completa=ejecutado · **sin_violaciones=fallido** | **1** violación, externa: `vault-backups` dos niveles por encima del repo (decisión de su dueño) |
| QG-03 | **PASS** (exit 0) | suite_junit=ejecutado (6332 tests, 0 fallos) · recorrido_e2e=ejecutado (27/27) | — |
| QG-04 | **PASS** (exit 0) | saneamiento=ejecutado · pip_audit=ejecutado («No known vulnerabilities found») · contencion=ejecutado · operaciones_destructivas=ejecutado | — |
| QG-05 | **PASS** (exit 0) | paridad_cli_mcp=ejecutado · ap40_contrato=ejecutado | — |
| QG-06 | **PASS** (exit 0) | construccion=ejecutado · wheel_contenido=ejecutado · instalacion_limpia=ejecutado | — |

**Estado fail-closed de la política** (el que decide si esto es publicable):
QG-00 `NOT_RUN` · QG-01 `NOT_RUN` · QG-02 `BLOCKED` · QG-03..QG-06 `BLOCKED`
por el prerrequisito QG-00 · **QG-07 `BLOCKED`** · **`liberable: false`**.

Dos correcciones para que los recibos midieran lo que deben medir (no para
relajarlos):

- El subcheck `suite_junit` exige el **recibo de procedencia** del JUnit
  (`<junit>.procedencia.json` con `sha`, `exit` y `junit_sha256`): sin él, el
  subcheck queda `no_ejecutado` (fail-closed, nunca PASS). El recibo declara
  el SHA evaluado, así que un JUnit de otro SHA no acredita este.
- El subcheck `pip_audit` audita el entorno del intérprete que se le pasa. Con
  una venv que solo llevaba `pip-audit`, lo que salía eran las
  vulnerabilidades del **pip de la propia auditoría** (PYSEC-2026-*, pip
  25.3), no las del producto. La venv se preparó con el paquete instalado y
  el pip subido: ahora mide las dependencias del producto y sale en 0.

### 3.1 Estado de las puertas

| QG | Estado | Motivo |
|---|---|---|
| QG-00 | **BLOCKED** | 10 divergencias sin ratificar (decisión A/B/C del propietario). El plan B está **preparado y no ejecutado**: `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` |
| QG-01 | **BLOCKED** | mismo reconciliador. La alternativa B del plan corrige un error de dirección del análisis de QA-RC-03 (la opción A crea el cruce que hay que eliminar) |
| QG-02 | **BLOCKED** | 13 de los 14 hallazgos eran contenido de **nuestra** semilla y están **CORREGIDOS** (`5178399`); queda 1, externo (AP-36, `vault-backups`), que es decisión de su dueño. Falta ratificar la política de certificación (propuesta, no aplicada) |
| QG-03..QG-06 | **BLOCKED** | recibos **PASS** (con artefacto y SHA-256 por subcheck), atrapados por el prerrequisito QG-00 (regla del catálogo) |
| QG-07 | **BLOCKED** | la CI ya no está en cola por facturación: **17 de 25 jobs verdes** en la corrida del SHA final, incluidos los 8 `validate` de Windows y Linux. Falta la conclusión, y la conclusión no llega mientras los **8 jobs `macos-latest` no arranquen**. Además QG-07 exige QA (verifica) + propietario (autoriza) |

## 4. Documentación reconciliada (con su fuente)

| Documento | Qué cambió |
|---|---|
| `audits/fase2/INFORME-READINESS-TERCEROS.md` | HEAD, candidato, estado REAL de la CI (la hipótesis de facturación, refutada), las 97 tools con su explicación (126 − 29 retiradas), QG-00..07, decisiones del propietario, alcance real (Windows y Linux medidos; macOS `NOT_RUN`) y el rótulo honesto: uso controlado por terceros técnicos, no distribución autorizada |
| `audits/handoff/PROTOCOLO-QA.md` | tabla de autoridades derivada campo a campo de `catalogo-qg.yaml` (QG-01 → `meta_toolkit - vault_arch`; QG-02 → `gobernanza - vault_norms`; QG-04 → QA **y** propietario; exenciones copiadas del catálogo) + rama de revisión activa `qa/review-release-cli-mcp-316623a-20261026` |
| `tests/test_protocolo_qg_contra_catalogo.py` | **guard de deriva** nuevo: el catálogo manda y el protocolo es un derivado; sin este test, un doc derivado se desfasaba sin que nadie lo viera |
| `audits/fase2/MATRIZ-CAPACIDAD-PRODUCTO.md` | capacidad declarada / implementada / empaquetada / probada / soportada / evidencia / riesgo, para CLI y MCP. Las cifras del PRD están caducadas (decía 116 y 117 tools; son 126 en catálogo, 97 expuestas, 14 con perfil `agente`; y 9 tools JS-native donde hay 2) |
| `audits/fase2/POLITICA-CERTIFICACION-PRODUCTO.md` | política **propuesta** (no aplicada) para QG-02: runtime limpio y sandbox canónico son alcances distintos y ninguno tapa al otro; lo único declarable es la contaminación externa, con dueño y fecha |
| `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` | la alternativa B preparada: interfaces, contratos, compatibilidad CLI/MCP, riesgos, pruebas, orden de commits, rollback y resultado esperado del reconciliador (10 divergencias → 0) |

## 5. Decisiones del propietario (nada de esto lo puede cerrar el ejecutor)

1. **Divergencias DIV-01..10** (cinco cruces): **B** con el matiz del plan
   (puerto de datos y proceso, no de símbolos) · A está descartada por
   dirección · C formaliza la deuda. La decisión sigue abierta.
2. **Política de QG-02**: ratificar / cambiar / rechazar la propuesta.
3. **`vault-backups`** (AP-36): purgar / mover / declarar con fecha y dueño.
4. **macOS en la CI**: habilitar los runners o declarar el alcance como
   Windows + Linux.
5. **Constitución arquitectónica** (DRAFT): ratificar, corregir o rechazar.
6. **Reescritura del historial publicado**: sí / no.

## 6. Bloqueos técnicos y externos

- **Técnicos**: ninguno abierto de esta ronda. Los tres defectos de CI están
  corregidos y comprobados; el defecto de `vault://graph`, corregido; el
  AP-47 del bootstrap, corregido; los 13 hallazgos de contenido de QG-02,
  corregidos.
- **Externos**: (a) los 8 jobs `macos-latest` no arrancan — infraestructura
  del repositorio/plan; (b) el dictamen QA de cierre; (c) las decisiones §5.

## 7. Riesgos

- La CI con historia completa es más lenta que con clon superficial: las 18
  pruebas de historia y las puertas que corren dentro de la suite hacen ahora
  trabajo real de git. Con `-n auto` y el JUnit como artefacto, el coste es
  medible por columna.
- `plan`, `batch` (olas, `--stop-on-error`), `--verify-integrity`, SSE/HTTP y
  la salida 130 están implementados y **no** los ejercita el E2E: es deuda de
  verificación, declarada en la matriz de capacidad.
- El planificador por impacto depende del grafo; su red es el conservadurismo
  (sin impacto determinable, suite completa).
- El auditor histórico mide parches, no blobs: `forma_secreto: 0` no prueba
  ausencia universal.

```text
COMMITS:   9e0bcd7 (fix CI: fetch-depth, detector MCP, SystemRoot)
           5178399 (fix QG-02: semilla canónica + reindex final)
           fc50d2b (fix MCP: vault://graph + códigos de error)
           89fbe4c (docs R12: protocolo + guard, plan B, política, matriz, informe)
           701f5d4 (fix CI: cifra de tests multiplataforma + JUnit como
           artefacto + ledger QG-02 regenerado)
           8b87b24 (fix CI: el paso vault_norms --list no depende del shell)
           408eb23 (fix suite: la idempotencia del SDD no compara el reloj)
           CANDIDATO DE PRODUCTO = 408eb23
           + el commit de este buzón (delta documental)
EVIDENCIAS: logs de los jobs de las corridas 40299732445, 40317033977,
           40326462714, 40335869688 y 40340865847 (descargados y analizados);
           clon local --depth=1 vs completo (19 fallos vs 129/129); repro de
           SystemRoot (3.9/3.12/3.14); cruce de segundo forzado del flake del
           SDD; medición en vivo del servidor MCP (97 tools, 7 recursos);
           auditoría del sandbox (14 -> 1); comparación de las listas de tests
           collectados (local vs CI); JUnit r12h con su recibo de procedencia.
RECIBOS:   QG-00..QG-06 del SHA 408eb23, con artefacto y SHA-256 por
           subcheck, en un directorio FUERA del arbol versionado. QG-03/04/05/06
           PASS; QG-00/01 fallan solo por las 10 divergencias sin ratificar y
           QG-02 solo por la violacion externa. La politica los deja
           BLOCKED y `liberable: false`. Ademas, el ledger de hallazgos QG-02
           queda regenerado con el codigo actual (15 fichas: 1 ABIERTO
           —AP-36, externo— y 14 CORREGIDO con su commit).
SOLICITUD QA: SÍ — dictamen de cierre sobre el SHA final `408eb23`, con la
           respuesta a `defc657` (los diez defectos, con su ficha) y el estado
           real de la CI. Si las decisiones del propietario y macOS siguen
           abiertas, el dictamen correcto es BLOCKED con esas causas.
```

---

# Respuesta del ejecutor a QA — R11 (optimización del harness y cierre de hallazgos)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico (ChatGPT) — protocolo y ramas de revisión declarados en `audits/handoff/PROTOCOLO-QA.md`
- **Fecha:** 2026-10-26
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `9919c57` (rama `qa/review-arquitectura-trazabilidad-e8f7aea-20261025`)
- **SHA inicial:** `45dca1be1e4367dc6d73d85192c04741a5ba755b`
- **SHA final de la ronda:** `fbfae57` · **Candidato de producto congelado:** `31dfa46`

## 1. Optimización medida (sin inventar porcentajes)

| Métrica | Antes | Después |
|---|---|---|
| Tests coleccionados | 6293 | 6306 |
| Suma de tiempos de test | 9511 s (158 min) | — (misma base de medición) |
| Reloj de pared de la suite | 1013 s con `-n auto` | 1013 s (paralelismo ~9,4× sobre la suma) |
| Tests que tocan la capa de arquitectura | 73 | 73 (pero ya no ensucian: el generador lee el árbol) |
| Regeneraciones del inventario dentro de tests | 1 por test, sobre el workspace | 1 por test, sobre un **árbol inmutable** |
| Aristas huérfanas del grafo | 49 (descartadas en silencio) | **0** (y registradas si aparecen) |
| Autorrelaciones `APPLIES_TO` vacías | 82 | **0** (norma → contexto) |
| Relación `DEPENDS_ON` | usaba nombres de contexto donde se esperaban IDs | usa IDs reales |

**Causas del coste identificadas con evidencia** (JUnit de la corrida, no
estimaciones): `test_fix_all` (149 s) y `test_nota_de_comandos` (109 s) ejecutan
**gates dentro de tests** (duplicación con las 26 puertas); la capa de
trazabilidad costaba 433 s en 73 tests por regenerar el inventario con un
escaneo del workspace.

**No se afirma ninguna mejora porcentual**: no hay dos corridas equivalentes con
el mismo código antes y después (el código cambió). Lo que sí se mide es la
estructura del coste y la eliminación de las causas identificadas.

## 2. Cambios en la arquitectura del harness

1. **Fuente inmutable**: `generar_inventario.py` lee del **árbol Git**
   (`git ls-tree`/`git show`), no del workspace. El inventario es una foto de un
   commit: determinista y sin carreras por construction.
2. **Un SHA inexistente falla** (`SHA_INEXISTENTE`, exit 2) en vez de fabricar
   un inventario. Antes generaba recursos de fuentes en vivo.
3. **Niveles de verificación** (QA-ARC-02): `descubierto → declarado →
   implementado → ejecutado → verificado → evidencia_acreditada → aceptado_qa →
   ratificado_propietario`, con `next_level_requires` obligatorio. El nivel sube
   **desde la evidencia real** (JUnit): 482 recursos con ejecución en verde, 5
   módulos verificados, 66 con evidencia acreditada. `status` se conserva por
   compatibilidad y significa lo que significaba.
4. **Relaciones tipadas** (15 tipos) con fundamento validado
   (`observada|declarada|inferida|pendiente`); una arista sin extremos NO se
   descarta en silencio: queda registrada.
5. **Planificador por impacto** (pilar N1): `planificar_pruebas.py` deriva los
   tests a ejecutar del **grafo**, con cierre **bidireccional** (un cambio
   alcanza a sus dependientes) y conservadurismo: sin impacto determinable
   exige suite completa. Contrato YAML con `selected_tests`, `omitted_tests`,
   `selection_justification` y `coverage_limitations`.
6. **Pruebas negativas del planificador**: dependencia transitiva omitida,
   aristas sin resolver, cambio sin relaciones, sin inventario, recurso sin
   tests, grafo roto.

## 3. Hallazgos QA-ARC

| ID | Estado | Qué |
|---|---|---|
| QA-ARC-01 | **CORREGIDO** | Relaciones tipadas completas, 0 huérfanas, `DEPENDS_ON` con IDs reales, 0 autorrelaciones vacías. Recurso pendiente: la cadena propósito→evidencia→dictamen se documenta en `trazabilidad-qg.md` |
| QA-ARC-02 | **CORREGIDO** | 8 niveles de verificación con evidencia; el inventario ya no presenta 686 "VERIFICADO" como certificación funcional |
| QA-ARC-03 | **PARCIAL** | 64 veredictos extraídos de las ramas QA (antes 56, ahora con las ramas nuevas). La extracción automática no puede deducir el commit correctivo de cada hallazgo: queda `NO_DETERMINADO` donde la fuente no lo dice |
| QA-ARC-04 | **PARCIAL** | Las 10 fichas clasifican naturaleza (movimiento / ficha / dependencia viva). El SHA del snapshot se toma del `.archify/extraccion-registro.json` cuando lo declara; si no, `NO_DETERMINADO` |
| QA-ARC-05 | **CERRADO** | AP-39 re-auditado con el código actual sobre un runtime **poblado** (75 ficheros, init exit 0): **0 violaciones, 0 AP-39**. El guion exige runtime poblado; un init fallido marcaba el escenario como INVÁLIDO (evita un "0 violaciones" falso) |
| QA-ARC-06 | **CORREGIDO** | Saneador de artefactos en el repo (`sanear_artefactos.py`); `comprobar_saneamiento` conforme |
| QA-ARC-07 | **CORREGIDO** | `source_sha` (árbol medido) y `publication_sha` (commit que publica) separados; el publicador de mediciones vive en el repo |
| QA-ARC-08 | **PARCIAL** | Las 15 fichas tienen impacto, causa, evidencia y acción. Las del sandbox (14) siguen sin `resolution_options` porque su resolución es documental y está en el backlog del vault de evidencia |

## 4. QG-00 a QG-07 (estado autologous)

| QG | Estado | Motivo |
|---|---|---|
| QG-00 | BLOCKED | reconciliador: 10 divergencias sin aceptar (decisión del propietario) |
| QG-01 | BLOCKED | mismo reconciliador |
| QG-02 | BLOCKED | 14 hallazgos del sandbox (documentales, bajo control) + contrato de certificación pendiente |
| QG-03..QG-06 | BLOCKED | recibos PASS, bloqueados por el prerrequisito QG-00 |
| QG-07 | BLOCKED | CI en `queued` |

## 5. Estado de la verificación

- **Puertas:** 26/26 sobre `0241ffe` y sobre el freeze `36c91e0`.
- **Suite de cierre:** **6307 passed / 13 skipped / 0 failed / 0 errores** en
  1068,67 s sobre `36c91e0` (JUnit `r11d`) — incluye la re-certificación de la
  suite `r11c` (6300 passed sobre `0241ffe`, 1076,40 s) y los 7 tests de la
  pirámide nuevas.
- **E2E:** 27/27 sobre `0241ffe` con wheel **reconstruida desde el código
  actual** (fix AP-39 dentro del paquete): wheel `79043404…73b066`, sdist
  `cc6b2224…57afbe`. El delta de `36c91e0` es documental (audits/, tests/, AGENTS.md):
  fuera del paquete distribuido, por lo que no se repite el E2E completo.
- **AP-39:** 0 violaciones en runtime poblado (75 ficheros).
- **Informe de readiness:** `audits/fase2/INFORME-READINESS-TERCEROS.md`
  (estado del proyecto para terceros, con cada cifra y su fuente).

## 6. Decisiones del propietario que siguen pendientes

1. Ratificar (o corregir) la Constitución arquitectónica (DRAFT).
2. Divergencias DIV-01..10: alternativa A / B / C para los cinco cruces.
3. Contrato de QG-02 (runtime limpio de certificación frente al vault de evidencia).
4. Purga de `vault-backups` fuera del vault (AP-36) — contenido inventariado.
5. Reescritura del historial publicado.

## 7. Bloqueos externos

- CI en cola: requiere acción del propietario sobre la cuenta (Settings →
  Billing → Actions). No se atribuye causa sin prueba.
- Dictamen QA sobre el SHA congelado.

## 8. Riesgos residuales

- La certificación integral (26 puertas + suite + E2E + recibos) debe repetirse
  sobre el SHA final de esta ronda: la evidencia actual es de 45dca1b.
- El planificador se apoya en el grafo; si el grafo queda desfasado respecto al
  código, la selección se queda corta. El conservadurismo (fallback a suite
  completa) es la red.
- Los 14 hallazgos del sandbox siguen abiertos: son deuda de contenido de
  evidencia, no de producto.

**SOLICITUD QA: SÍ** — sobre el SHA final de esta ronda, con la re-ejecución
integral y los recibos externos.

---

# Respuesta del ejecutor a QA — GOAL Release CLI + MCP (ronda R09, cierre técnico)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico
- **Fecha:** 2026-10-25
- **Rama:** `work/release-cli-mcp-20261025`
- **Dictamen QA respondido:** `a9e0143b5e246e2766fece5273bd7bfa20632707`
- **SHA inicial de la ronda:** `29c1a15cfcb212dedbcf1b6794c238fd815a4aa5`
- **SHA CANDIDATO CONGELADO:** `31dfa462e87f5dcdb703e649e840e826a136ba50`
- **Árbol:** limpio en el SHA congelado; `main` intacta (`1c34754`); PR #1, #2 y #3 sin fusionar (#3 DRAFT)

## GOAL: RELEASE CLI + MCP PARA TERCEROS

**ESTADO: READY_FOR_QA_WITH_EXTERNAL_BLOCKER.** Las correcciones técnicas de
R09-A..D están ejecutadas, probadas y publicadas; las 26 puertas y la suite
completa están en verde sobre el SHA congelado; los recibos se emitieron
ejecutando los verificadores de verdad. **Los únicos pendientes son decisiones
del propietario y la CI externa**, y QG-00..QG-07 declaran su estado real
(abajo), sin PASS falso.

## QA-RC-02g — resultados independientes por subcheck (CERRADO, `532f19e`)

Cada subcheck tiene verificador, comando (o función interna), exit code,
artefacto **propio** y SHA-256; la puerta solo pasa si **todos** pasan. Se
eliminó la autocertificación (un `exit 0` repartido a los subchecks). Salida
vacía ⇒ `degradado`. El comando de pruebas se ejecuta como pytest
(`python -m pytest <fichero> -q`), no como script. Negativas: subcheck fallido,
no ejecutado, salida vacía, artefacto individual ausente, artefacto manipulado,
subcheck ausente, QG-04 sin `pip_audit`, QG-06 sin instalación limpia, QG-00
sin reconciliador.

## QA-RC-02h — CLI del colector (CERRADO, `532f19e`, `001120c`, `31dfa46`)

`main()` ya no pasa `jobs_ci` a `colectar()`. Nueva CLI `--ejecutar` (ejecuta
verificadores y emite recibos **fuera** del árbol) separada de la evaluación;
`--recibos`, `--e2e-json`, `--suite-xml`, `--pip-audit-python`,
`--paridad-venv/--paridad-runtime`; códigos de salida explícitos (2 en error de
argumentos) y JSON final válido. La identidad del checkout (HEAD == SHA y árbol
limpio) se verifica **antes** de ejecutar (los verificadores escriben
artefactos de runtime propios) y viaja al dictamen. Probada como **proceso
real** por subprocess.

## QA-RC-02i — CI vinculada al run exacto (CERRADO, `532f19e`)

Jobs del endpoint del run seleccionado, con paginación y `total_count`; sin
identidad de run, con conclusión nula, con duplicados, con jobs desconocidos o
con paginación incompleta no se acredita; sin jobs o sin permisos ⇒ BLOCKED.

## QA-RC-05 — recorrido completo de terceros (CERRADO, `5a8395c`)

Sandbox nuevo por ejecución; hash del **fichero persistido**; cuarentena
identificada por el conjunto antes/después; cliente MCP **secuencial** con ids
correlacionados y plazo global; restore en destino limpio comparado por
**inventario y hashes**; reinstalación que conserva los datos.
**Resultado real: 27/27 pasos.**

## SUITE / SKIPS / PUERTAS / RECORRIDO E2E (sobre el SHA congelado)

| Medición | Resultado |
|---|---|
| 26 puertas | **26/26 en verde** |
| Suite completa | **6270 passed · 13 skipped · 0 failed** (16:17) |
| Recorrido E2E | **27/27** |

Los 13 skips declaran no aplicable en este entorno (symlink sin privilegios,
MCP en vivo sin su variable, etc.).

## WHEEL / SDIST / HASHES

| Artefacto | sha256 |
|---|---|
| `vault_obsidian_architecture-41.23-py3-none-any.whl` | `858f14073563d0f9ec81e5347bbf58637028da0575da758e7f9c00057815d9c1` |
| `vault_obsidian_architecture-41.23.tar.gz` | `22cf5d0c749499ecff040436f05b77df83552d29fe5ee4e691472c068d02d472` |

## QUALITY GATES — estado auténtico del SHA `31dfa46`

| QG | Estado | Evidencia / motivo |
|---|---|---|
| QG-00 | **BLOCKED** | su recibo es FAIL: el subcheck `reconciliador_archify` falla con **10 divergencias de inventario sin aceptar** (el snapshot de Archify, que documenta otra revisión, sigue apuntando a `vault_norms_engine` y las fichas del registro cambiaron al mover los cruces a `vault_norms`). `identidad_git`, `arbol_limpio` y `saneamiento`: ejecutados |
| QG-01 | **BLOCKED** | mismo reconciliador; `vault_arch`: ejecutado (ok) |
| QG-02 | **BLOCKED** | `puertas_26` y `auditoria_completa`: ejecutados (`completo: true`); `sin_violaciones`: **fallido** — la auditoría del sandbox canónico arroja 14 hallazgos (AP-07, AP-36, AP-64, CN-03) |
| QG-03 | **BLOCKED** | recibo PASS (suite JUnit con recibo de procedencia + recorrido E2E) pero bloqueado por el prerrequisito QG-00 |
| QG-04 | **BLOCKED** | recibo PASS (saneamiento, `pip_audit` sin vulnerabilidades, contención, operaciones destructivas) pero bloqueado por QG-00 |
| QG-05 | **BLOCKED** | recibo PASS (paridad CLI/MCP **5/5 CONFORME**, 97 tools MCP; AP-40 exit 0) pero bloqueado por QG-00 |
| QG-06 | **BLOCKED** | recibo PASS (construcción, contenido de la wheel, instalación limpia) pero bloqueado por QG-00 |
| QG-07 | **BLOCKED** | CI en `queued` (runs 40244460688, 40245587377, 40245754464 y posteriores) y prerrequisito QG-00 |

**Ningún PASS se declara sin ejecución real**: cada subcheck tiene su artefacto
y su hash en `%TEMP%\opencode\qg-recibos-final` (fuera del árbol versionado).

## CI / PR #3

- CI **queued**. Sin prueba concluyente no se atribuye la causa a facturación;
  el diagnóstico con evidencia de API está en `audits/fase2/CI-diagnostico.md`.
  La capacidad que falta es de la cuenta (Settings → Billing → Actions).
- PR #3 **DRAFT**, sin merge. PR #1 y #2 sin fusionar. `main` intacta.

## ARQUITECTURA (QA-RC-03) — DECISIONES DEL PROPIETARIO

1. **Ratificar o corregir el movimiento de los cinco cruces** de
   `vault_norms_engine` a `vault_norms`: el código distribuible ya no importa
   módulos excluidos (`shipped_imports_of_excluded: []`), pero el snapshot de
   Archify y las fichas del registro siguen describiendo el sitio anterior, y
   el reconciliador del repo lo refleja en 10 divergencias. Sin esta decisión
   QG-00 y QG-01 no acreditan.
2. **Fijar el contrato de QG-02**: ¿"cero violaciones" se mide sobre el sandbox
   canónico (que contiene 14 hallazgos deliberados) o sobre un runtime limpio
   de certificación? El dato medido está arriba; la decisión es del dueño.

Alternativas A/B/C con impacto, riesgo y recomendación:
`audits/fase2/ESTADO-RC.md`.

## SEGURIDAD

`pip_audit` sin vulnerabilidades conocidas (dependencia PyYAML); wheel sin
trazas, sin tests y sin material ajeno; contención verificada; operaciones
destructivas con rollback verificado por hash (23 pruebas).

## COMMITS

`532f19e` (02g/h/i) · `5a8395c` (recorrido de terceros) · `001120c` (identidad
del checkout) · `31dfa46` (subchecks derivados y verificadores especiales) ·
este informe.

## RECIBOS / EVIDENCIAS

- Recibos externos (`%TEMP%\opencode\qg-recibos-final`): un artefacto + sha256
  por subcheck y manifiesto agregado por puerta.
- JUnit de la suite + recibo de procedencia (`sha`, `exit`, `junit_sha256`).
- `audits/fase2/{colector_qg.py, recorrido_terceros_r07.py, ESTADO-RC.md,
  CI-diagnostico.md}`, `tests/test_colector_qg.py` (30),
  `tests/test_vault_init_clean.py` (23).

## RIESGOS

- QG-07 depende de una CI que no se ejecuta.
- QG-00/QG-01 dependen de la decisión del propietario sobre el inventario.
- El auditor histórico mide parches, no blobs (`forma_secreto: 0` no prueba
  ausencia universal).

## BLOQUEOS EXTERNOS

1. CI en cola (acción del propietario sobre la cuenta).
2. Ratificación del movimiento de los cruces (QG-00/QG-01) y del contrato de
   QG-02.
3. Decisión sobre reescritura de historia.

**SOLICITUD QA: SÍ** — revisión independiente del SHA congelado `31dfa46`, con
los recibos externos y las 10 divergencias de inventario pendientes de decisión.

---

# Respuesta del ejecutor a QA — fase 2, remediación post-QA (R01–R05)

- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico
- **Fecha:** 2026-10-25
- **Rama:** `fase2/deuda-y-product-readiness-20261025`
- **SHA del dictamen QA:** `2b8c87d`
- **SHA base de ejecución:** `2b8c87d`
- **SHA final publicado:** el commit de este documento (R05)
- **SO / terminal / Python:** Windows, PowerShell 5, Python 3.14.3
- **Estado del árbol:** sin cambios pendientes al cerrar
- **`main`, PR #1 y PR #2:** intactos; sin fusionar; sin `reset --hard` ni `push --force`

## Alcance ejecutado (R01–R05)

R01, R02 y R03 son correcciones efectivas. R04 es **solo diseño**: `scripts/vault_init.py` no se ha tocado.
TD-0003 y Q04–Q07 siguen sin implementar, por orden expresa.

| Tarea | Estado | Commit | Qué resuelve | Evidencia |
|---|---|---|---|---|
| R01 / H-F2-01 | COMPLETADA | `b9fb71d` + `dc63367` | El identificador personal ya no está incrustado (se deriva del entorno) y la cobertura pasa a blobs de toda la historia; 10 pruebas | `logs/H-F2-01-exposicion-historica.{json,txt}`, `logs/R01-auditor-historico.txt` |
| R02 / H-F2-02 | COMPLETADA | `08f9746` + `6a3ab78` | Los efectos externos se detectan por hash de contenido (creados/modificados/eliminados), con la lectura fallida como no verificable; 23 pruebas | `logs/L3-paridad-cli-mcp.txt` (5/5 CONFORME) |
| R03 / H-F2-03 | COMPLETADA | `2b5d141` | La política de QG se ejecuta: QG-00 prerrequisito, QG-02 condicionado por TD-0003, QG-07 con CI concluyente; 9 pruebas negativas | `logs/R03-politica-qg.txt` |
| R04 / TD-0008 | DISEÑO | `584470e` | Cuarentena atómica, máquina de estados de 8 fases con rollback, `--confirm`, 11 pruebas propuestas; sin cambio de comportamiento | `R04-diseno-td0008.md` |
| R05 | COMPLETADA | `24eb0a9`, `116595c` y este commit | Higiene de publicación (el auditor ya no reproduce nombres; fixtures compuestos en runtime) y carga por ruta de los instrumentos de `audits/fase2/`; buzón e informe de cierre | `logs/R05-cierre-orden.txt` |

## Verificación ejecutada

| Verificación | Resultado |
|---|---|
| `python -m pytest tests/test_fase2_hf201_privacidad.py` | 10 passed |
| `python -m pytest tests/test_fase2_paridad_fail_closed.py` | 23 passed |
| `python -m pytest tests/test_fase2_politica_qg.py` | 9 passed |
| `python audits/fase2/comprobar_saneamiento.py` | exit 0 |
| `python scripts/vault_gate.py --strict` | **25/26** — `criterios` (AP-57) rojo |
| `python -m pytest tests/ -q -n auto --tb=short` | **5 failed, 6184 passed, 12 skipped** — los 5 son los de AP-57 ya reproducidos en `2b8c87d` |

**El rojo de `criterios` es preexistente**, no de esta orden: se reprodujo igual en un worktree
`--detach 2b8c87d` (los mismos 3 `.yaml` de evidencia leídos como `frontera_no_declarada`).
No se ha ampliado ninguna baseline ni deshabilitado ninguna puerta.

## CI

Los cinco runs de la rama siguen en `queued` (el último, `40183930953` / `6a3ab78`). No se ha
cancelado ni relanzado ninguno, ni se ha modificado ningún workflow. Por ello **QG-07 = BLOCKED**
con `CI_PENDIENTE`, tal como aplica el evaluador de R03.

## Bloqueos

1. **CI en cola** → QG-07 BLOCKED (dato del proveedor).
2. **`criterios` / AP-57**: falso positivo preexistente sobre 3 YAML de datos; su corrección exige
   decidir el criterio del guard y añadir su test (fuera del alcance de esta orden).
3. **TD-0003**: QG-02 BLOCKED mientras el envelope no publique el estado de ejecución por control.
4. **Exposición histórica**: sigue en los blobs publicados; reescribir historia requiere autorización
   del propietario.

## Solicitud de QA

Revisar R01–R04, y decidir (a) el tratamiento del falso positivo de `criterios` y (b) la autorización
del diseño de TD-0008 para pasar a implementación.

---

## Lote de correcciones del dictamen QA (H-F2-04, H-F2-05, H-F2-06)

Publicado sobre el dictamen `cb3233a`, en commits separados:

| Hallazgo | Corrección | Commit | Evidencia |
|---|---|---|---|
| **H-F2-04** (P1) — la política daba `liberable=true` sin SHA ni evidencias | `sha_objetivo` obligatorio (7-40 hex) + evidencia obligatoria por gate; ausente → `EVIDENCIA_AUSENTE`, de otro SHA → `EVIDENCIA_DE_OTRO_SHA` | `0a583da` | 15 pruebas; repro posterior da `liberable=false` |
| **H-F2-05** (P1) — YAML de datos leído como frontera ejecutable (AP-57) | `yaml_es_ejecutable()`: `.github/` = ejecutable; claves de primer nivel de workflow = ejecutable aunque esté mal ubicado; resto = datos | `8b01bdb` | 7 pruebas nuevas; 50 passed en AP-57/AP-46; `criterios` ok, `new_copies []`, baseline 2 |
| **H-F2-06** (P2) — alcance histórico sobreafirmado | Se inspeccionan **parches** (declarado), `blobs_inspeccionados=0`, métricas separadas (`commits_considerados=52`, `con_exposicion=10`, `ficheros=64`, `deltas=120`, `errores=0`) y prueba de historia sin hallazgos | `d175917` | `logs/H-F2-01-exposicion-historica.{json,txt}`, `logs/R01-auditor-historico.txt` |

**Registro canónico:** `TD-0010`, `TD-0011` y `TD-0012` en `audits/fase2/inventario-deuda.yaml`, estado `corregida` con su commit.
**Informe del lote:** `audits/fase2/logs/R06-dictamen-correcciones.txt`.

**Verificación de este lote:** puertas **26/26** (`vault_gate --strict`), suite completa **6203 passed / 12 skipped / 0 failed**, `comprobar_saneamiento` exit 0.

**Lo que sigue pendiente y por qué:** TD-0003/Q04–Q07 (cambio de producto, requiere autorización; QG-02 `BLOCKED`), TD-0008 (diseño publicado; `vault_init --clean` intacto, requiere autorización), CI en cola (QG-07 `BLOCKED` con `CI_PENDIENTE`) y la exposición histórica del blob de `b9fb71d`, que sólo el propietario puede decidir reescribir.

---

# Respuesta del ejecutor a QA — ronda 1B (histórico, se conserva)
- **Emisor:** agente local (ejecutor técnico)
- **Destinatario:** QA arquitectónico
- **Fecha:** 2026-10-25 (hora local del ejecutor, UTC-6)
- **Rama:** `audit/archify-governance-20261024`
- **SHA leído de instrucciones QA:** `bf4003f69bc84ac1ffa0fd13fc2bfe41045cc046` (dictamen de ronda 1)
- **SHA base de ejecución:** `bf4003f` (estado tras la sincronización E01)
- **SHA final publicado:** `559e204` (anexo de CI del cierre; la lista completa de commits de la ronda 1B está en la tabla de ejecución y en la sección de cierre técnico)
- **SO / terminal / Python:** Windows, PowerShell 5, Python 3.14.3
- **Estado del árbol local al terminar:** limpio (`git status --porcelain` vacío); `main` intacto, PR #1 sin fusionar
- **SHA base de la ronda 1 (referencia QA):** `f3aaafc34a4ca719070a55f642452d52c107b58d`

## Resumen de cambios

Siete commits publicados entre `bf4003f` y la publicación de este informe (uno por unidad, push tras cada uno):

| Tarea | Estado | Commit | Archivos | Pruebas | Resultado | Evidencia |
|---|---|---|---|---|---|---|
| E01 sincronización | COMPLETADA | `94bf46e` | `audits/handoff/logs/R1B-E01-sincronizacion.txt`, `audits/handoff/logs/2026-10-24-R1-respuesta-ejecutor.md` | `git merge --ff-only` (exit 0) | fast-forward limpio `f6a5387..bf4003f`, sin pérdidas; informe de ronda 1 preservado (QA lo leyó como plantilla) | `R1B-E01-sincronizacion.txt` |
| E02 observabilidad del ledger | COMPLETADA | `e925bef` | `tests/test_ap39_contrato.py` | unittest AP-39: 6/6 OK, exit 0 | `vocabulary_recorded == -1` y `vocabulary_introduced == [tag]` añadidos al caso del ledger roto; aserciones previas conservadas; no es vacua (None o >=0 harían caer el test) | `R1B-Q02-unittest.txt` |
| E03 precedencia de root | COMPLETADA | `01a9d8f` | `tests/test_puerto_notas_indexables.py` | unittest enumeración: 4/4 OK, exit 0; pytest de ambos ficheros de contrato: 10 passed | `root=self.otra` manda sobre el ambiente apuntando a `self.raiz`; sin contaminación, con filtros, orden estable y equivalencia con el criterio del dominio | `R1B-Q03-unittest.txt` |
| E04a saneamiento de evidencias | COMPLETADA | `5c27601` | `audits/handoff/logs/2026-10-24-Q00-baseline.md` | `pytest tests/test_publicacion_limpia.py`: 6 passed, exit 0 | ruta local del autor sustituida por marcador neutro; se conserva SO, terminal, Python y forma de la ruta | `R1B-E04a-saneamiento.txt` |
| E04b fixtures arquitectónicos | COMPLETADA | `031abfb` | `tests/test_puente_sin_hogar.py`, `tests/test_puertos_verificados.py` | pytest de ambos ficheros: 167 passed, exit 0 | los cuatro tests usaban como ejemplo símbolos publicados como puertos en la ronda 1; reencaminados preservando su capacidad de detección, demostrada con par positivo/negativo (al retirar el puerto, el cruce reaparece con su clave exacta) | `R1B-E04b-fixtures.txt` |
| E04c corrección H4 | COMPLETADA | `2eabcfe` | `README.md`, `tests/test_quickstart_del_readme.py` | test afectado: 2 passed, exit 0 (antes: `ValueError: No closing quotation`, exit 1 en f3aaafc); regresión relacionada: 44 passed | defecto PREEXISTENTE reproducido en f3aaafc en worktree aislado; portados SOLO los dos hunks del commit local de main `0a06696` (no publicado en GitHub — anotado para QA); sin cambios de producto | `R1B-E04c-h4.txt` |
| E04e CI | COMPLETADA (actualización final tras el push de este informe) | `bc741dc` + cierre | `audits/handoff/logs/R1B-E04e-ci.txt` | consulta `gh run list` + API de jobs | 13 runs de la rama en cola, 1 en curso (SHA de QA), 4 completados con fallo en SHAs PREVIOS a la rama; yaml = job de wheel, JSON-RPC = tests que miran historial git truncado en CI; clasificación: preexistentes; dictamen CI: PENDIENTE DE VALIDACIÓN | `R1B-E04e-ci.txt` |
| E04d validación integral | COMPLETADA | `988f5b7` | logs bajo `audits/handoff/logs/` (11 ficheros) | ver sección Validación | suite 1 failed/6140 passed/11 skipped (el 1 era higiene de la propia evidencia, corregido y reverificado 6/6); puertas 24/26 con las dos causas documentadas | `R1B-E04d-validacion.txt` |
| E05 informe | COMPLETADA | este commit | `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` | — | este documento | — |

## Validación (entorno aislado: worktree dedicado en `2eabcfe`, sandbox propio inicializado con la herramienta de la rama `vault_standard_upgrade --to v41.23`, v20→v41.23 con migraciones; sin editar `applied_version`; sin tocar el sandbox compartido)

| Verificación | Comando | Exit | Resultado |
|---|---|---|---|
| Entorno | `python --version` | 0 | Python 3.14.3 |
| AP-39 | `python -m unittest discover -s tests -p "test_ap39_contrato.py"` | 0 | Ran 6 tests in 15.276s — OK |
| Enumeración | `python -m unittest discover -s tests -p "test_puerto_notas_indexables.py"` | 0 | Ran 4 tests in 24.399s — OK |
| Arquitectura estricta | `python scripts/vault_arch.py --check --strict` | 0 | ok: true; `new_off_port_crossings: []`; `off_port_total: 5`; `off_port_baseline: 5`; `broken_ports: []` |
| Gobernanza | `python scripts/vault_gate.py --strict` | 1 | **26 puertas: 24 pasan, 2 fallan** (ver Incidencias) |
| Suite integral | `python -m pytest tests/ -q -n auto --tb=short` | 1 → corregido | 1 failed, 6140 passed, 11 skipped en 1405.85s; el único fallo era una ruta local en DOS LOGS PROPIOS de esta ronda, corregida y reverificada (`test_publicacion_limpia`: 6 passed, exit 0) |
| GitHub Actions | `gh run list --branch audit/... --limit 30` | 0 | 13 runs de la rama en cola (ninguno ejecutado); 4 completados con fallo en SHAs previos a la rama; **CI: PENDIENTE DE VALIDACIÓN** |

Condiciones innegociables de arquitectura: **cumplidas** (`new_off_port_crossings == []`, `off_port_total == 5 <= 5`, `off_port_baseline == 5`, baseline sin tocar — 5 entradas D–H, ni una más).

Aislamiento demostrado: del sandbox compartido solo cambiaron `.tool-trace.json` (21:46, ANTES de la corrida aislada) y `.voice-counter` (22:16, incremento del propio ejecutor al correr la comparación del noop en el checkout principal); la corrida aislada escribió únicamente en el sandbox del worktree. Recuento de ficheros idéntico: 131 antes y después.

## Incidencias

**Fallos preexistentes (no introducidos por la rama):**
1. **H4** — el ejemplo `vault_write` del README estaba roto desde antes de la ronda (reproducido en `f3aaafc` en worktree aislado). Corregido en `2eabcfe` con autorización condicional del propietario. NOTA DE TRAZA: la corrección de `main` vive en el commit local `0a06696`, sin publicar en GitHub; QA no puede cotejarlo en el remoto hasta que se publique.
2. **Puerta `noop` (AP-37) en rojo sobre un sandbox v41.23 limpio** — el modo ejecutado corre los ejemplos documentados contra una copia del sandbox, y el ejemplo de `vault_frontmatter_completar` asume una nota que `vault_init` no crea. Mismo commit: exit 0 contra el sandbox del checkout principal (que conserva esa nota de corridas previas) y exit 1 contra el limpio. Clasificación: AMBIENTAL + PREEXISTENTE. Se deja en rojo documentado — no se fabricó estado para sacar verde.
3. **CI en cola** — 13 runs de la rama sin ejecutar por el límite de concurrencia de runners (el run en curso, de un SHA previo a la rama, sostiene la cola con 24 jobs). Los 4 runs completados con fallo son de SHAs anteriores a `f3aaafc`: `ModuleNotFoundError: No module named 'yaml'` en "Product gates (wheel)" y fallos de tests que miran el historial git en "Validate Vault Spec". Clasificación: PREEXISTENTES.

**Regresiones corregidas (introducidas y cerradas por esta ronda):**
1. Ruta local publicada en la evidencia de Q00 → saneada (`5c27601`); el propio guard la detectó y su test vuelve a estar en verde.
2. Cuatro fixtures que usaban como ejemplo símbolos publicados como puertos → reencaminados con capacidad de detección demostrada (`031abfb`).
3. Dos rutas residuales en los logs de esta misma ronda (citadas dentro del "ANTES" de E04a y en un traceback de E04c) → saneadas durante E04d; el único fallo de la suite aislada era eso, ya reverificado en verde.

**Bloqueos ambientales:** CI sin ejecutar (cola de runners); documentado, sin cancelaciones ni relanzamientos.

**Pendientes:** dictamen de QA sobre esta ronda; publicación del commit `0a06696` de `main` (para que H4 sea cotejable en remoto); Q04–Q07 siguen en ANÁLISIS, sin cambios de comportamiento.

## Evidencias (audits/handoff/logs/)

`R1B-E01-sincronizacion.txt` · `2026-10-24-R1-respuesta-ejecutor.md` (informe de ronda 1, preservado) · `R1B-Q02-unittest.txt` · `R1B-Q03-unittest.txt` · `R1B-E04a-saneamiento.txt` · `R1B-E04b-fixtures.txt` · `R1B-E04c-h4.txt` · `R1B-E04d-validacion.txt` · `R1B-suite.txt` · `R1B-gates.txt` · `R1B-arch-strict.txt` · `R1B-sandbox-init.txt` · `R1B-docstaleness-recheck2.txt` · `R1B-noop-recheck.txt` · `R1B-E04e-ci.txt` · `2026-10-24-Q00-baseline.md` (ronda 1, saneado)

## Solicitud formal

**¿Se solicita aceptación QA?: SÍ**

**Estado de aceptación: PENDIENTE DE QA.** No se declara aprobada la ronda ni la suite: la aceptación corresponde exclusivamente a QA. Decisiones que se dejan en manos de QA: (1) aceptación o no de la corrección H4 y su trazabilidad parcialmente local; (2) el dictamen sobre la puerta `noop` en entorno limpio (ambiental/preexistente) y si su arreglo entra en una ronda futura; (3) la asignación de Q04–Q07.


---

# CIERRE TÉCNICO DE LA RONDA 1B (actualización posterior al informe)

**SHA final: `559e204`** · commits del cierre: `f24a9b8` (fix AP-37), `a813094` (evidencias gates/arch/suite/entorno), `559e204` (anexo CI) y este commit.

## Hallazgos

### H-QA-01 — AP-37 / no-op silencioso — RESUELTO
- **Causa identificada:** el ejemplo completo de `vault_frontmatter_completar` (`--path 07_Knowledge/x.md --apply`) presupone una nota que `vault_init` no crea. En un banco v41.23 limpio la tool rehúsa con NOTE_NOT_FOUND, no escribe y la entrada quedaba `sin_escritura_sin_motivo`; en un sandbox con corridas previas escribía — la medida dependía del residuo.
- **Dónde estaba el defecto:** NO en la implementación ni en el contrato de AP-37, sino en la DECLARACIÓN DE PRECONDICIONES del ejemplo. El mecanismo determinista ya existía (`FICHEROS_DEL_EJEMPLO` en `scripts/vault_noop_audit.py`) y su propio comentario prometía «los dos sanadores» sin declarar el segundo.
- **Archivos modificados:** `scripts/vault_noop_audit.py` (+8 líneas).
- **Justificación:** declarar la precondición con la plantilla `nota` existente —que no trae `createdAt/updatedAt/cia_*/agent`, justo lo que el completador añade— de modo que el `--apply` escriba de verdad en banco limpio. No se convierte NOTE_NOT_FOUND en éxito: la tool AHORA ESCRIBE y el banco lo mide.
- **Evidencia anterior:** `R1B-CIERRE-AP37-antes.txt` (exit 1, tool en `sin_escritura_sin_motivo`).
- **Evidencia posterior:** `R1B-CIERRE-AP37-despues.txt` (exit 0, tool en `medidas` = escritura real).
- **Pruebas:** test afectado verde en banco limpio; tests específicos del auditor (`test_ap37_ejecutado` + `test_ejemplos_de_escritores`): 22 passed.
- **Estado:** RESUELTO sobre entorno limpio y reproducible. **Riesgo residual:** el modo ejecutado de AP-37 sigue siendo sensible al estado del sandbox en general (documentado); otros ejemplos pueden tener dependencias no declaradas que solo afloran en entornos limpios.

### H-QA-02 — doc_staleness — VERIFICADO EN AGREGADO
- La regeneración ya no se hizo a mano: se usó el **bootstrap canónico del propio repo** (`tests/sandbox_fixture.py --bootstrap`), que genera los 7 artefactos y los verifica.
- **Evidencia:** `R1B-CIERRE-gates.txt` — `gates_total: 26, passing: 26, failing: 0`, exit 0, 521.1s, sobre el mismo entorno y SHA que la suite.
- **Estado:** VERIFICADO. Sin riesgos residuales conocidos.

### H-QA-03 — Suite integral — CERO FALLOS
- **Comando:** `python -m pytest tests/ -q -n auto --tb=short` — exit 0.
- **Resultado:** **6141 passed, 0 failed, 11 skipped**, 2 warnings, 1019.94s. (6141 + 11 = 6152 = la cifra que publica el derivado de conteos.)
- **Evidencia:** `R1B-CIERRE-suite.txt`.
- **Estado:** CERO FALLOS sobre el SHA final, sin omisiones artificiales (11 skips = los históricos de la suite).

### H-QA-04 — Arquitectura y contratos — INVARIANTES INTACTOS
- `python scripts/vault_arch.py --check --strict` → exit 0; `broken_ports: []`; `new_off_port_crossings: []`; `off_port_total: 5`; `off_port_baseline: 5`.
- La corrección de AP-37 no toca fronteras, contratos ni propietarios: añade una precondición declarada de un ejemplo.
- **Evidencia:** `R1B-CIERRE-arch.txt`. **Estado:** INVARIANTES CONSERVADOS.

### H-QA-05 — Integración continua — PENDIENTE DE VALIDACIÓN EXTERNA
- Consulta fresca tras el push final: todos los runs de la rama (incluido el del fix AP-37 y el del cierre) siguen **en cola**; los 4 completados con fallo siguen siendo de SHAs anteriores a `f3aaafc` (preexistentes, investigados en `R1B-E04e-ci.txt`).
- **Evidencia:** `R1B-CIERRE-ci.txt`. **Estado:** CI: PENDIENTE DE VALIDACIÓN EXTERNA. No se atribuye aprobación de CI a los resultados locales.

## Resultados

```text
AP-37:             PASA EN SANDBOX LIMPIO (fix publicado, par antes/después con escritura real)
QUALITY GATES:     26/26, exit 0 (521.1s)
ARCHITECTURE:      exit 0; broken_ports [], new [], total 5, baseline 5
FULL TEST SUITE:   6141 passed, 0 failed, 11 skipped, exit 0 (1019.94s)
GITHUB ACTIONS:    PENDIENTE DE VALIDACIÓN EXTERNA (todo en cola; fallos observados preexistentes)
MAIN:              INTACTO (local 4efcf22, origen 1c34754; ningún push a main)
ISOLATED BRANCH:   audit/archify-governance-20261024 @ 559e204, publicada
```

## Incidente documentado del cierre (transparencia)

La validación requirió cuatro pasadas. Las tres primeras fallaron por el ENTORNO, no por el código: (1) la reconstrucción borró el `tool-spec.json` VERSIONADO —el bootstrap de la suite lanzó INTERNALERROR y cinco puertas cayeron en cascada—; (2) restaurarlo con `vault_manifest --bootstrap` generó una spec de introspección (159 activas) en lugar del contrato curado —los tests de campos la rechazaron con razón—; (3) fijar `VAULT_ROOT` rompió los tests que ejercitan la detección, y el orden gates-antes-de-suite sobre un sandbox no-ready hizo que la suite lo reconstruyera y limpiara. La pasada 4 usó el procedimiento canónico del propio repo (`tests/sandbox_fixture.py --bootstrap`) y dio verde completo. Detalle completo: `R1B-CIERRE-entorno.md`.

## Dictamen solicitado

Se solicita a QA una de: **ACEPTADO / ACEPTADO CON OBSERVACIONES / REQUIERE CORRECCIONES / BLOQUEADO**, sobre las evidencias de este cierre. La CI permanece como validación independiente pendiente; su estado no invalida ni aprueba el cierre local documentado.


---

# ACUSE DE RECIBO — dictamen de cierre técnico (2026-10-25)

- **Dictamen leído:** `audits/handoff/RESPUESTA-QA.md` en el commit `d78604a` de `origin/audit/archify-governance-20261024` (sincronizado por fast-forward; árbol limpio).
- **Dictamen:** ACEPTADO CON OBSERVACIONES — cierre técnico LOCAL de ronda 1B.
- **Registro del ejecutor:** H-QA-01 a H-QA-04 aceptados en alcance local; H-QA-05 (CI) PENDIENTE. La observación de QA sobre la trazabilidad de los tres intentos fallidos se conserva tal cual: es parte del valor del registro.
- **Vigilancia activa del ejecutor:** cuando CI tenga capacidad de ejecutar los runs de la rama, se documentará estado, matriz multiplataforma, dependencias de wheel (incluido PyYAML) y pruebas JSON-RPC antes de cualquier solicitud de autorización de distribución.
- **Sin acciones iniciadas:** ni merge de PR #1 a `main`, ni Q04–Q07, ni release — todas requieren decisión explícita del propietario.

**Estado de la ronda 1B: CERRADA EN ALCANCE LOCAL, a la espera de las decisiones del propietario.**

---

# FASE 2 — Deuda tecnica, Quality Gates y Product Readiness · LOTE L1 (2026-10-25)

- **Rama de fase 2:** `fase2/deuda-y-product-readiness-20261025`, derivada de `ef77a7b` (punta de la rama auditada, con el acuse del dictamen).
- **Rama auditada de ronda 1B:** `audit/archify-governance-20261024` — **congelada**, sin commits nuevos. `main` intacta (local `4efcf22`, origen `1c34754`).
- **SHA base del descubrimiento:** `ef77a7b19a6aaa5e8a5bf776181ab887b7ee4587` · Python 3.14.3 · Windows/PowerShell 5.
- **Alcance de L1:** inventario de los diez contextos y reconciliacion del snapshot de Archify con el codigo actual. **No se ha modificado codigo de producto** (las herramientas de `audits/fase2/` son de auditoria, no del producto).

## Resultados de L1

| Comprobacion | Resultado |
|---|---|
| Contextos inventariados | **10/10**, con puertos, modulos y prohibiciones desde el registro vivo (68 puertos en total) |
| Pares de cruce del presupuesto | **23/23 coinciden con el registro y con ficha IDENTICA** (objetivo, dueno, revisado, cadencia, por que): cero divergencias |
| Dependencias del snapshot (37, a nivel de fichero) | Colapsan a **23 pares de contexto, los 23 vigentes**: reconciliacion completa |
| Accesos fuera de puerto del snapshot (8) | **5 vigentes** (los de Q04–Q07, con su cruce y su simbolo) y **3 resueltos en ronda 1** con su commit (Q01/Q03) |
| Anclas del puente | **2/2** coinciden, con motivos identicos |
| Delta total contra el snapshot | `indices` con 3 puertos mas (los publicados en ronda 1) y `meta_toolkit` con 1 modulo mas |

**Instrumentos creados (reproducibles):** `audits/fase2/reconciliar_archify.py` (confronta snapshot y codigo) y `audits/fase2/matriz_contextos.py` (genera la matriz desde el registro). Evidencia: `audits/fase2/logs/L1-reconciliacion-archify.txt` y `.json`.

## Hallazgos (6; registro canonico en `audits/fase2/inventario-deuda.yaml`)

| ID | Sev | Hallazgo | Estado |
|---|---|---|---|
| TD-0001 | **P1** | El job de CI de la wheel ejecuta las puertas del producto sin instalar el paquete → `ModuleNotFoundError: 'yaml'` → ese job no puede pasar nunca; el defecto esta en el workflow, no en los metadatos (PyYAML SI esta declarado) | vigente |
| TD-0003 | **P1** | Un control que no puede cargar su dependencia (3 bloques `except → pass` en `vault_norms_engine.py:151,179,196`) informa cero hallazgos: la ausencia de hallazgos no significa ejecucion | vigente |
| TD-0002 | P2 | Las trazas runtime del servidor MCP (958 KB) caen dentro del paquete mapeado `vault_toolkit.mcp` y `exclude-package-data` no las cubre | no verificada (se mide en L3) |
| TD-0005 | P2 | Seis documentos de producto (2 PRD, contrato de runtime, instalacion limpia, `gaps.md`, `PUERTAS.md`) sin clasificar | no verificada (L4) |
| TD-0006 | P2 | Las baselines estan por encima de su objetivo declarado con plazo activo: `off_port_crossings` 5 vs objetivo 4; `crossings` 37 vs objetivo 30; ambos con `fecha_limite: 2027-03-31`. El mecanismo mide que no crecen, no la aproximacion | vigente |
| TD-0004 | P2 | Reconciliacion del snapshot de Archify | **corregida** (instrumento ejecutable y repetible) |

**P0: ninguno** con la evidencia reunida. El recorrido MVP de L3 puede cambiarlo; si apareciera perdida de datos o corrupcion del runtime, se avisa de inmediato.

## Un hallazgo que condiciona L2

Las dos fichas de cruce con `objetivo: a_eliminar` y `fecha_limite: 2027-06-30` nombran **exactamente** los modulos de Q04–Q07:

- `gobernanza → meta_toolkit`: «`vault_norms_engine` importa `vault_smoke` y `vault_mcp_catalog` en diferido para auditar el catalogo» → **Q04 + Q05**
- `gobernanza → autoria`: «`vault_norms_engine` -> `vault_voice`: presentacion colgada del motor» → **Q06**

O sea: Q04–Q07 **no son deuda desconocida**; el repo decidio el 2026-08-14 eliminarlos (no formalizarlos como puertos), con plazo. L2 investiga el COMO (inversion, adaptador o contrato), con las tres pruebas exigidas, sin implementar.

## CI: PENDIENTE DE VALIDACION EXTERNA (documentado, sin cancelar)

| Run ID | SHA | Estado | Conclusion | Clasificacion |
|---|---|---|---|---|
| 40168004595 | `a813094` | queued | — | PENDIENTE (cola de runners) |
| 40161384740 | `f24a9b8` | queued | — | PENDIENTE |
| 40159084620 | `bcc1f8b` | queued | — | PENDIENTE |
| 40147533176 | `8885c79` | completed | failure | **PREEXISTENTE**: 24/25 jobs en rojo; `yaml` ausente en «Product gates (wheel)» y fallos de tests que miran el historial git truncado en el checkout de CI |
| 40147250440 / 40147115820 / 40147025723 | `3adc050` / `08a2ddf` / `40d81e6` | completed | failure | **PREEXISTENTES**, SHAs anteriores a `f3aaafc` |

**Causa conocida:** limite de concurrencia de runners; un run antiguo (`069616a`, de un commit de QA de la ronda 1) sigue en curso y sostiene la cola. **No se cancela ninguna ejecucion** (condicion 2 de la orden). **Causa pendiente de investigacion:** por que el job de la wheel no instala el paquete (TD-0001) — su evidencia local llega en L3. La CI pendiente no impide investigar, pero **impide aprobar un release estable**.

## Riesgos y bloqueos

1. **La comparacion CLI↔MCP y el recorrido MVP son el unico punto que puede abrir un P0** (instalacion limpia, persistencia, contencion). Se ejecutan en L3 con la wheel construida y un venv nuevo fuera del checkout.
2. **El metodo de comparacion tiene una asimetria conocida:** el lado MCP es un `.mjs` de 97 KB con su propio catalogo, y el lado CLI un registro de operaciones en Python. La paridad se medira sobre resultados NORMALIZADOS, no sobre igualdad literal de respuestas de transporte.
3. **La deuda de documentacion (TD-0005) puede contener hallazgos ya corregidos:** `docs/sdd/gaps.md` es un historico y se reconciliara antes de contarlo (L4).
4. **Ningun hallazgo se ha cerrado sin evidencia:** TD-0002 y TD-0005 siguen como `no_verificada` hasta que L3/L4 las midan.

## Siguientes acciones

1. Revision tecnica de este L1 por QA (el buzon de QA sigue siendo suyo).
2. Con el visto: **L2** (investigacion de Q04–Q07 con causa, contrato, decision y tres pruebas por control).
3. En paralelo, **L3** (wheel + venv + paridad CLI/MCP + recorrido MVP) y **L4** (documental + seguridad + reconciliacion historica).
4. Decisiones que se piden al propietario y QA: corregir TD-0001 (workflow) cuando L3 lo demuestre; autorizar o no la implementacion de TD-0003 cuando L2 traiga el diseno; fijar la prioridad entre deuda de entrega y preparacion de producto.

**Estado de la fase 2: PLANIFICACION EN CURSO. No se declara aprobada ni el producto.**

---

# FASE 2 — LOTE L3 (2026-10-25): VIAJE REAL DE DISTRIBUCION

- **Rama:** `fase2/deuda-y-product-readiness-20261025` · **SHA base:** `ef77a7b` (derivada de la rama auditada, congelada).
- **Entorno:** Windows 11, Python 3.14.3, Node 24.14.0, red disponible (PyPI accesible).
- **Artefacto:** `vault_obsidian_architecture-41.23-py3-none-any.whl` (1.661.092 bytes, 705 miembros), construido con la tool de la rama y con el interprete que REPLICA el job de CI (solo `build` instalado).
- **Alcance:** TD-0001 (correccion autorizada), TD-0002 (verificacion), recorrido MVP y paridad CLI<->MCP. **Sin codigo de producto modificado** (unica excepcion: el workflow de CI).

## 1. TD-0001 — causa raiz, correccion y verificacion

**Causa raiz (confirmada y reproducida):** `tests/clean_install_gate.py` importa el paquete (`vault.meta_toolkit.distribucion` -> `frontmatter_parsing` -> `import yaml`) en el **interprete del runner**, y el job de la wheel solo instalaba `build`: la dependencia PyYAML, **declarada** en `pyproject.toml`, nunca llegaba a estar. El gate moría antes de medir.

**Correccion (minima, cross-platform):** paso nuevo `Install wheel (artefacto y dependencias declaradas)` antes de `Run product gates`, con `shell: bash` —el mismo shell que ya usa el paso de SBOM de ese job— para que el glob de la wheel se expanda igual en los tres sistemas. No se tocan producto, tests ni cobertura.

| Momento | Entorno | Resultado |
|---|---|---|
| Antes | venv 'runner' (solo `build`) | `clean_install: FAIL` — `ModuleNotFoundError: No module named 'yaml'` (clean_install_gate.py:48) |
| Despues | el mismo venv + `pip install dist/*.whl` | `clean_install: PASS`, `memory_e2e: PASS`, **Overall: ALL PASS**, exit 0 |

Evidencia: `audits/fase2/logs/L3-TD0001-antes.txt` y `L3-TD0001-despues.txt`.

**Pendiente:** el run de CI del SHA corregido (la rama de fase 2 necesita un PR para que dispare el evento `pull_request`: decision del propietario). Por eso TD-0001 queda en estado **parcial**: la correccion esta aplicada y verificada en local, la confirmacion de CI no existe.

## 2. TD-0002 — hipotesis refutada

La wheel **no lleva trazas runtime**: 0 trazas entre 705 miembros, tanto construida desde el checkout como desde una copia limpia sin `.git` (ambas dan 1.661.092 bytes, 4 ficheros en `vault_toolkit/mcp/`). El motivo es **declarativo**: `[tool.setuptools.package-data]` nombra para `vault_toolkit.mcp` exactamente los cuatro ficheros que deben viajar. **Estado: falso positivo** (no aplica). Evidencia: `audits/fase2/logs/L3-wheel-contenido.txt`.

## 3. Recorrido MVP — 16/16, desde el artefacto y fuera del checkout

Ejecutado de verdad (`audits/fase2/recorrido_mvp.py`, reejecutable):

| # | Paso | Resultado |
|---|---|---|
| 1 | venv nuevo FUERA del checkout | OK |
| 2 | wheel instalada en ese venv | OK |
| 3 | script de consola `vault` instalado | OK |
| 4 | runtime externo creado con `vault init` | OK |
| 5 | nota escrita por CLI (`vault run vault_write`) | OK |
| 6 | servidor MCP **del artefacto** (`vault_toolkit/mcp/…`) presente | OK |
| 7 | handshake MCP (`initialize` -> `notifications/initialized`) | OK (protocolo 2024-11-05) |
| 8 | `tools/list` | OK — **97 tools** expuestas |
| 9 | leer la nota por MCP (`vault_read`) | OK |
| 10 | modificarla por MCP (`vault_write`) | OK |
| 11 | consultarla por MCP (`vault_search`) | OK |
| 12 | **persistencia tras reiniciar el proceso MCP** (proceso nuevo) | OK — la linea escrita por MCP sobrevive |
| 13 | verificar por CLI el cambio hecho por MCP | OK |
| 14 | **contencion**: intento de escritura fuera de la raiz | OK — **rechazado**, no se escribio fuera del runtime |
| 15 | la nota existe en disco dentro del runtime | OK |
| 16 | `vault status` ve el runtime sano | OK (exit 0) |

Evidencia: `audits/fase2/logs/L3-recorrido-mvp.txt`.

**Dos desviaciones fueron mias y las corrigio el instrumento, no el producto:** el primer intento escribio por CLI un cuerpo de 2 lineas y el gate **AP-11** lo rechazo con exit 7 (correcto: el gate exige tres; el write por MCP, con tres, paso); y mi criterio de "lectura correcta" miraba la ausencia de una palabra que el frontmatter lleva. Ninguna de las dos era un defecto del producto.

## 4. Paridad CLI <-> MCP — 5/5, con el verificador de contrato en verde

Medida sobre el **mismo runtime**, con fotografia y restauracion del estado entre adaptadores (sin eso, la segunda llamada de una escritura mide un update donde la otra midio un create: divergencia del guion, no del producto).

| Operacion | CLI | MCP | Coincide |
|---|---|---|---|
| `vault_read` (inexistente) | `ok:false` | `ok:false` | si |
| `vault_search` | `ok:true, total:0` | `ok:true, total:0` | si |
| `vault_list` | `ok:true` | `ok:true` | si |
| `vault_write` (crea) | `ok:true, created:true` | `ok:true, created:true` | si |
| `vault_write` (actualiza) | `ok:true, updated:6` | `ok:true, updated:6` | si |

**Nivel de contrato:** `vault_mcp_catalog --check-params` (el verificador AP-40 del repo, el mismo que corre en CI) → **exit 0**: el esquema MCP y el argparse de cada tool concuerdan.

Matriz: `audits/fase2/matriz-paridad-cli-mcp.md` · Log: `audits/fase2/logs/L3-paridad-cli-mcp.txt`.

## 5. Limitaciones de L3 (lo que NO se ha medido)

1. **Multiplataforma y versiones:** todo esto es Windows + Python 3.14.3 + Node 24. La matriz declarada (ubuntu/macos, Python 3.9-3.12) solo la ejecuta la CI, y la CI esta en cola: **no hay veredicto multiplataforma**.
2. **Seguridad completa:** L3 cubre contencion (traversal rechazado) y aislamiento (origen en `site-packages`, checkout no importable — lo afirma la puerta `memory_e2e`). El barrido de seguridad (secretos, superficie del transporte MCP, dependencias, cadena de suministro) es de L4.
3. **Cobertura de la paridad:** 5 operaciones medidas sobre 97 tools expuestas. La paridad del resto no esta medida; el verificador de contrato (AP-40) si cubre todas las tools.
4. **Q04–Q07:** sin tocar (investigacion autorizada para L2, implementacion pendiente de dictamen).
5. **P0: ninguno** detectado en el viaje real: no hubo perdida de datos, ni corrupcion del runtime, ni escritura fuera de la raiz.

## 6. Riesgos y bloqueos

1. **CI en cola** → TD-0001 queda parcial y QG-07 no puede cerrarse. No se cancela ninguna ejecucion.
2. **La rama de fase 2 no tiene PR** → el workflow (eventos `push` a main/master y `pull_request` a main/master) no se dispara para ella. Decision del propietario: abrir un PR de la rama de fase 2.
3. **La paridad medida es una muestra**: 5 operaciones de 97. QG-05 debe declarar ese alcance (muestra + verificador de contrato) o exigir cobertura total.
4. **Observaciones, no hallazgos:** `vault status` exige el argumento `runtime` mientras `vault init` no lo pide (ergonomia, exit 2 de uso); el gate AP-11 rechazo correctamente un cuerpo de dos lineas — el gate de contenido funciona en el artefacto instalado.

## 7. Siguientes acciones

1. Revision tecnica de L3 por QA (su buzon sigue siendo suyo) y decision sobre el PR de la rama de fase 2.
2. Con el visto: **L4** (documental, seguridad e historia) o **L2** (Q04–Q07, solo investigacion), segun la prioridad que fije el propietario.
3. Cerrar TD-0001 cuando exista un run de CI con conclusion sobre el SHA corregido.

**Estado de la fase 2: PLANIFICACION Y DIAGNOSTICO EN CURSO. No se declara aprobada la fase ni el producto.**

---

# FASE 2 — L3 (correcciones) y L2 (investigacion) · 2026-10-25

- **Rama:** `fase2/deuda-y-product-readiness-20261025` · **SHA base:** `ef77a7b` (rama auditada, congelada) · **Entorno:** Windows 11, Python 3.14.3, Node 24.14.0.
- **Alcance de este tramo:** las tres correcciones que QA pidio sobre L3, la apertura del PR autorizado y la investigacion de L2 (Q04–Q07). **Sin implementar** Q04–Q07.

## 1. Correcciones de L3 (una por commit, con prueba y evidencia)

| Correccion | Commit | Que se hizo | Evidencia | Prueba |
|---|---|---|---|---|
| **H-L3-01** saneamiento | `bc1a1e6` | Tres logs estaban en **UTF-16 sin BOM** (3859/3184/1186 bytes NUL) y varios conservaban la estructura de la maquina detras del marcador. Todo a UTF-8 y toda ruta absoluta a `<RUTA-LOCAL>`. Se anade `audits/fase2/comprobar_saneamiento.py` (ejecutable) + `tests/test_fase2_logs_saneados.py` | `H-L3-01-saneamiento.txt` | Antes: **13 problemas, exit 1**. Despues: **conforme, exit 0**. Test: 8 passed (2 nuevos + los 6 del guard del repo) |
| **H-L3-02** paridad fail-closed | `d657fb0` | La evaluacion vive en `evaluar()` (funcion PURA): falla si AP-40 no sale 0, falta un campo obligatorio, divergen codigos o significado del error, divergen los efectos, un caso requerido no se ejecuto, o llega `isError`/`error de transporte` que contradice al otro adaptador | `H-L3-02-paridad-fail-closed.txt` | **11 tests** (control positivo + 10 negativos). Real: 5/5, AP-40 exit 0, 97 tools, **CONFORME** |
| **H-L3-03** timeout del harness | `44a880e` | `readline()` bloqueante -> hilo + `queue.get(timeout=...)`. El cliente acepta el comando, lo que permite probar el silencio. Registrado como **TD-0007 (instrumento, P3, corregida)**: NO es un defecto demostrado del servidor MCP. Ademas los scripts de auditoria **sanean su propia salida** (el verificador los habia cazado) | `H-L3-03-timeout-mcp.txt` | Servidor mudo -> error de timeout en ~2s (con la version antigua se colgaba). Con MCP instalado: **2 passed** |

**Exposicion historica (investigada, sin reescribir historia):** `git grep` sobre `origin/main`, `origin/audit/…` y `origin/fase2/…` → **0 ficheros** con ruta local real, con el nombre del autor o con forma de credencial. No hay nada que contener ni rotar, y no se hizo force-push ni se reescribio historia: el estado de la ronda 1B se integro con un **merge** de los commits de QA (`1eca182`, `4f6170f`).

## 2. PR en borrador (autorizado)

**PR #2** — `fase2/deuda-y-product-readiness-20261024` → `main`: **DRAFT**, OPEN, MERGEABLE, **sin auto-merge**, sin merge de PR #1. El cuerpo identifica expresamente **los cambios heredados de la ronda 1B** (10 commits, dictamen `d78604a` "ACEPTADO CON OBSERVACIONES") y lo que añade esta rama. Al abrirlo se disparo el evento `pull_request`: **run `40173539210`** para el SHA de la rama.

## 3. L2 — investigacion de Q04–Q07 (TD-0003), sin implementar

**Hecho OBSERVADO y medido:** los tres controles del estandar viven en `scripts/vault_norms_engine.py::_checks_estandar` (AP-40 lineas 141-152, AP-42 159-180, AP-43 186-197), cada uno con `except (ImportError, OSError, ValueError): pass`. La funcion **no devuelve nada**: su unico canal es `flag(...)`. El envelope (`vault/gobernanza/auditoria_runtime.py`) publica `ok: True` **hardcodeado**, `total_violations`, `by_norm` y `violations`, y **no tiene ningun campo que declare que controles se ejecutaron**.

**Demostracion reproducible** (`audits/fase2/demostrar_control_degradado.py`): con la dependencia sana el control aparece en `by_norm` con su hallazgo; con la dependencia rota **desaparece y el envelope no avisa**. Medido en las tres familias.

**Causa:** el contrato de salida no tiene estados de ejecucion; "no se pudo mirar" y "no se encontro nada" son la misma senal.

**Consumidores analizados:** la CLI `--audit --strict` decide **solo** por `total_violations` (lineas 584-594) → un control degradado baja el contador a 0 y la puerta sale con exit 0 (**LECTURA DE CODIGO**: no se pudo aislar el exit code en un vault sintetico, y asi se declara); la puerta de coherencia compara `by_norm` antes/despues y veria "sin cambios" si el control no se ejecuto en ninguno de los dos pases; y el puerto publicado `auditar_normas` hereda el defecto.

**Lo que el registro ya decidio (y acota la via):** los dos cruces que sostienen estos accesos estan declarados `objetivo: a_eliminar` con `fecha_limite: 2027-06-30` → la intencion es **eliminar**, no formalizar. Propuesta: **inversion + contrato de estados** (`ejecutado | degradado | fallido | no_ejecutado`, mas un campo hermano `completo` para no cambiar `ok`). Se descarta formalizar `check_params`/`load_baseline`/`coverage` como puertos: contradice la ficha vigente y deja el defecto vivo.

**Pruebas propuestas** (NO implementadas): positiva (control sano con estado `ejecutado`), negativa (envelope sin estados no conforme), dependencia fallida (el control se declara no ejecutado y la auditoria no se presenta como limpia), regresion de consumidores (la CLI con un control degradado sale con codigo distinto de cero) y equivalencia (envelope sano identico al actual mas `checks`).

Documento completo: `audits/fase2/L2-analisis-q04-q07.md` · Evidencia: `audits/fase2/logs/L2-control-degradado.json` · TD-0003 actualizada en el inventario.

## 4. Estado y limites

- **CI: PENDIENTE DE VALIDACION EXTERNA.** El PR #2 ha disparado el workflow para la rama; hasta que un run tenga conclusion **no se declara CI aprobada**, y **QG-07 sigue pendiente**. No se cancela ni relanza ninguna ejecucion.
- **Sin merger a `main`**, `main` intacto, PR #1 sin fusionar, ronda 1B cerrada.
- Alcance de la paridad: **cinco** casos de 97 tools expuestas (el contrato de todas lo cubre el verificador AP-40).
- Validacion local: Windows + Python 3.14.3 + Node 24; la matriz ubuntu/macos × 3.9–3.12 depende de la CI.
- El release **no** se declara listo: QG-07 y la validacion multiplataforma siguen pendientes.

**Estado de la fase 2: L1, L3 (con sus tres correcciones) y L2 (investigacion) entregados; L4 (documental, seguridad e historia) pendiente de autorizacion. La aceptacion corresponde a QA.**

---

# FASE 2 — CIERRE DE PENDIENTES Y QUALITY GATES (2026-10-25)

**SHA base:** `b680ac8` (dictamen QA de L2/L3) · **SHA final:** `8a852de` · **Árbol:** limpio · **`main`: intacto** (local `4efcf22`, origen `1c34754`) · **PR #2 en DRAFT sin fusionar** · **PR #1 sin fusionar**.

## C1 — Cierre de observaciones de L3

### H-L3-04 · Exposición histórica — RESUELTO CON INVENTARIO
Mi afirmación anterior («0 ficheros con ruta real en ninguna rama publicada») era una lectura del **árbol** de cada ref, no de la historia: QA la señaló bien y **era materialmente incorrecta para el historial**. El nuevo instrumento (`auditar_exposicion_historica.py`) recorre **todos** los commits alcanzables que tocaron las evidencias, extrae cada blob y lo clasifica **publicando solo huellas sha256** de los valores (correlacionables sin mostrarlos).
- **Inventario:** 20 commits con exposición en 9 ficheros; categorías: `ruta_local` 45 · `nombre_personal` 11 · `nul_utf16` 6 · **`forma_secreto` 0**.
- El commit que QA nombró (`44f6f89`) está en el inventario ✓.
- **Clasificación:** dato personal y de entorno; **sin credenciales** → no hay incidente que escalar ni nada que rotar.
- **Contención propuesta al propietario:** (a) documentar y asumir, o (b) reescritura de historia con `git filter-repo`/BFG **con autorización expresa** (y avisando de que GitHub puede conservar los blobs tocados, de modo que la reescritura no garantiza la retirada).
- **Prevención verificada:** el verificador de saneamiento (exit 0) + los scripts de auditoría que **sanean su propia salida** + la prueba negativa de que el verificador detecta ruta real, UTF-16 y clave.
Evidencia: `audits/fase2/logs/H-L3-04-exposicion-historica.{txt,json}` · commit `1888cf0`.

### H-L3-05 · Paridad con identidad por escenario — RESUELTO
- Cada caso lleva `case_id` propio (READ_MISSING, SEARCH_HITS, LIST_FOLDER, WRITE_CREATE, WRITE_UPDATE); el verificador exige ejecutar **cada id**, rechaza **duplicados** y **no previstos**.
- **Efectos reales medidos**: estado del runtime antes/después por pasada (creados, modificados, eliminados y huellas con contenido normalizado —timestamps y uuid enmascarados—), telemetría de la llamada excluida por diseño, restauración del estado entre adaptadores, y comprobación de que **no se modifica nada fuera del runtime**.
- **17 pruebas**: control positivo + los 7 negativos que exigía QA (caso omitido, duplicado, no previsto, AP-40 roto, campo ausente, errores divergentes, exit code contradictorio, efectos divergentes, huellas distintas, modificación fuera del runtime) + los previos adaptados.
Evidencia: `audits/fase2/logs/H-L3-05-paridad-escenarios.txt` · commit `78807ab`.

### H-L3-06 · Plazo global del cliente MCP — RESUELTO
Un único deadline monotónico gobierna la llamada; las líneas con otro id **no lo renuevan**. Pruebas: servidor silencioso (timeout en el plazo), respuesta válida, mensajes con otro id, **notificaciones continuas sin la respuesta esperada** (el caso adversarial: el goteo no alarga el plazo) y terminación del proceso. 4 passed + 1 skipped sin servidor; 5 passed con él. Evidencia: `audits/fase2/logs/H-L3-06-plazo-global.txt` · commit `1448c4d`.

## L4 — Auditoría documental, de seguridad y de deuda histórica

- **L4-A documental** (`inventario-documental.yaml`, 8 documentos clasificados): el Quick Start del README es **INCOMPLETO** (mezcla la superficie del checkout con la del producto instalado — DOC-0001); ARQUITECTURA.md, PUERTAS.md, INSTALACION-LIMPIA.md y los ADR **VIGENTES** (el primero byte a byte con su derivado); los PRD **NO_VERIFICADOS** (DOC-0006); `.archify/` vigente como evidencia auxiliar.
- **L4-B seguridad**: contención presente y usada (**103 ficheros** con `assert_within_vault`) y medida en el recorrido (el escape es rechazado); el MCP **exige initialize** (error −32002); **cero tools de gobernanza** en la superficie CLI/MCP (96 operaciones); la wheel declara `PyYAML>=6.0` y `Requires-Python >=3.9`; sin trazas runtime en el artefacto. Pendientes: auditoría de dependencias, symlinks/TOCTOU y validación de `params` contra el `inputSchema`.
- **L4-C histórica** (`gaps.md` de v36.0 → v41.23): H1 **CORREGIDA** (`vault_undo` existe); H2 **PARCIAL** (14/167 con `--dry-run`); K3/K4 **PARCIALES** (21 `slugify`, 14 `utcnow`); D3 **VIGENTE** → **TD-0008**; resto NO_VERIFICADO (quedan para un lote de reconciliación ampliada).
- **L4-D nueva deuda**: **TD-0008 (P1)** `vault_init --clean` destruye el runtime sin copia previa; **TD-0009 (P2)** el Quick Start del README no declara su supuesto; TD-0010 confirmada (TD-0006). **Descartados con motivo**: ARQUITECTURA desfasada (mi instrumento comparó contra otro derivado), trazas en la wheel (medido: 0), tools de gobernanza por MCP (medido: 0), credenciales publicadas (medido: 0).

## Quality Gates — catálogo formal propuesto

`audits/fase2/catalogo-qg.yaml`: QG-00..QG-07 con el contrato completo (id, name, version, purpose, owner, acceptance_authority, scope, checks, required_evidence, pass/fail_criteria, blocking_policy, timeout_policy, waiver_policy, results). Reutilizan: las 26 puertas (QG-02), `vault_arch`+catálogo+esquemas+reconciliador (QG-01), la suite+`memory_e2e`+recorrido MVP (QG-03), `comprobar_saneamiento`+guard de secretos+contención (QG-04), el verificador fail-closed de paridad+AP-40 (QG-05), `clean_install_gate`+contenido del artefacto (QG-06) y la decisión de release (QG-07). **Invariantes de gobernanza** incluidos (no-executado ≠ PASS, control degradado ≠ completo, resultado ≠ SHA distinto, baseline sin ampliar, waiver con propietario/motivo/vencimiento, release sin CI local-only, resultado histórico ≠ prueba actual, documentación ≠ capacidad sin comprobar).

## TD-0003 — Diseño final (sin implementar)

`audits/fase2/L2-diseno-final.md`: inventario completo de consumidores, inversión de dependencias (los duenos ejecutan sus controles y entregan el resultado; el motor lo colecciona), contrato aditivo de estados (`checks[]` con `ejecutado|degradado|fallido|no_ejecutado` + `completo`), fail-closed de CLI y puerta de coherencia, migración en tres fases revertibles con plan de rollback, siete tests propuestos y riesgos. La vía C (formalizar los cruces como puertos) se descarta: contradice las fichas `a_eliminar` con plazo. **No se ejecuta ningún commit de implementación sin autorización adicional.**

## CI — PENDIENTE DE VALIDACIÓN EXTERNA

Tres runs de la rama de fase 2 en `queued` (últimos SHAs 44a880e, 47f5beb, 73e9592, 1c788e3, 8a852de, bcbe6e8); los 4 completados con fallo siguen siendo de SHAs **previos** a la rama (preexistentes). Log: `audits/fase2/logs/CI-cierre.txt`. No se cancela ni relanza nada. **QG-07: BLOCKED.**

**Estado de la fase 2: L1, L2 (investigación), L3 con sus tres correcciones, L4 y QG formalizado entregados. La aceptación corresponde a QA.**