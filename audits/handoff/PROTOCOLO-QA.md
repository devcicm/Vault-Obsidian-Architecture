# Protocolo QA — agente, autoridad y ramas de trabajo

Referencia canónica de cómo opera el par QA ↔ ejecutor en este release. Fuente:
`INSTRUCCIONES-PARA-EJECUTOR.md` (órdenes), `audits/fase2/catalogo-qg.yaml`
(autoridad de aceptación) y los dictámenes del propio QA en `RESPUESTA-QA.md`.

## 0. Estado vigente (R23, 2026-10-28)

Las secciones 1 a 5 son la cronología hasta R22 y se conservan tal cual. Lo
que rige hoy es esto:

- **Ramas:** el repositorio quedó en dos, `main` y
  `work/release-cli-mcp-20261025`. Las 23 ramas `qa/*`, `proposal/*`,
  `audit/*` y `fase2/*` se borraron después de verificar que sus puntas son
  ancestros de la rama de trabajo (merge `ours` `b1a1614`): ningún SHA se
  perdió. El texto de cada dictamen está en `audits/qa-archivo/`. Las tablas
  de ramas de §4 y §5 nombran ramas que ya no existen en el remoto.
- **Decisiones del propietario:** DEC-01..06 asentadas
  (`ACTA-DECISIONES-PROPIETARIO-2026-10-28.md`).
- **QA independiente:** para v41.23, el propietario decidió no esperar el
  dictamen antes de publicar (DEC-06). La aceptación se apoya en los recibos
  del colector y en la CI externa del SHA. Un dictamen posterior sobre el
  mismo SHA sigue siendo bienvenido, y lo que encuentre se trata como
  incidencia del release publicado.
- **Candidato y matriz REL vigentes:** `audits/fase2/CANDIDATO-RELEASE.yaml`
  y §9.ter de `audits/fase2/INFORME-READINESS-TERCEROS.md`.
- **CI:** Windows + Linux, Python 3.9–3.12, 27 jobs (suite en 2 shards y
  puertas en job propio). La forma de la matriz la lee el colector del
  workflow.

## 1. El círculo de dos agentes

Dos agentes colaboran por turnos; el propietario transmite entre rondas:

| Agente | Qué hace | Qué NO hace |
|---|---|---|
| **QA arquitectónico (ChatGPT)** | investiga, traza y planifica; revisa la evidencia publicada en GitHub; emite dictámenes | no ejecuta pruebas; no modifica código; no fusiona `main` |
| **Agente local (ejecutor)** | implementa y verifica en checkout real; entrega evidencia en su buzón | no ratifica decisiones del propietario; no escribe el buzón de QA |

Principio común declarado en los dictámenes: `NOT_RUN ≠ PASS`. Ningún dictamen
ni respuesta afirma ejecuciones que no consten como artefacto (comando, exit
code, salida).

## 2. Autoridad por Quality Gate (fuente: `audits/fase2/catalogo-qg.yaml`)

Derivada campo a campo del catálogo: `owner` (DUEÑO), `acceptance_authority`
(ACEPTACIÓN) y `waiver_policy` (EXENCIÓN). Quien EJECUTA cada gate es el agente
local (QA no ejecuta pruebas); el DUEÑO es el módulo/actor al que pertenece el
control en el código, y la ACEPTACIÓN decide si el resultado habilita release.
Un doc derivado que discrepan de esta tabla se detecta con
`tests/test_protocolo_qg_contra_catalogo.py`.

| QG | Dueño (catálogo) | Aceptación | Exención (waiver) |
|---|---|---|---|
| QG-00 | `agente ejecutor` | **QA arquitectónico** | no permitida: la identidad no se exime |
| QG-01 | `meta_toolkit - vault_arch` | **QA arquitectónico** | solo con decisión del propietario y fecha de vencimiento (nunca para seguridad) |
| QG-02 | `gobernanza - vault_norms` | **QA arquitectónico** | no permitida |
| QG-03 | `agente ejecutor` | **QA arquitectónico** | no permitida |
| QG-04 | `agente ejecutor` | **QA arquitectónico + propietario** | solo con propietario, causa, mitigación y vencimiento; nunca para integridad de datos |
| QG-05 | `agente ejecutor` | **QA arquitectónico** | solo con la divergencia documentada y aceptada por QA |
| QG-06 | `agente ejecutor` | **QA arquitectónico** | no permitida |
| QG-07 | `propietario del producto` | **QA arquitectónico (verifica) + propietario (autoriza)** | una condición pendiente (como CI) deja la puerta BLOCKED, nunca PASS |

## 3. Buzones de handoff (regla de propiedad)

| Fichero | Escribe | Uso |
|---|---|---|
| `audits/handoff/INSTRUCCIONES-PARA-EJECUTOR.md` | QA | órdenes de entrada del ejecutor |
| `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` | agente local | buzón normalizado de entrega (evidencia por subcheck) |
| `audits/handoff/RESPUESTA-QA.md` | **QA exclusivamente** | dictámenes; **solo lectura** para el ejecutor — nunca sobrescribir |

## 4. Ramas de trabajo

- **Rama de implementación:** `work/release-cli-mcp-20261025` — única rama de
  trabajo del ejecutor; no se fusiona nada y `main` queda intacta.
- **Ramas de trabajo QA:** convención `qa/review-<ámbito>-<sha>-<fecha>`, son
  ramas remotas aisladas donde QA registra su revisión. El ejecutor **no las
  crea, no las empuja y no las fusiona**; las lee para extraer el dictamen
  vigente.

| Rama QA | Estado |
|---|---|
| `qa/review-release-cli-mcp-0580b7e-20261025` | dictámenes de rondas anteriores emitidos |
| `qa/review-release-cli-mcp-4c66fc2-20261025` | ídem |
| `qa/review-release-cli-mcp-4595aea-20261025` | ídem |
| `qa/review-release-cli-mcp-4396273-20261025` | ídem |
| `qa/review-release-cli-mcp-29c1a15-20261025` | dictamen `a9e0143` (revisión de release intermedia) |
| `qa/review-arquitectura-trazabilidad-e8f7aea-20261025` | dictamen `9919c57` (8 hallazgos QA-ARC-01..08); respondidos por la ronda R11 |
| `qa/review-release-cli-mcp-316623a-20261026` | **ACTIVA** — dictamen `defc657` (CI real corriendo: corrida 40299732445 con 8 fallos reales — checkout superficial, MCP/PyYAML en Windows y env de hijo sin SystemRoot — más reconciliación documental); la ronda R12 es su respuesta |

Ramas auxiliares históricas del ejecutor: `audit/archify-governance-20261024`
y `fase2/deuda-y-product-readiness-20261025` (cerradas; no participan en el
release actual).

| Rama de revisión | Qué contiene |
|---|---|
| `qa/review-release-cli-mcp-408eb23-20261026` | dictamen `e30e668` (R12 auditada: macOS ejecutó y falló — 21/25 jobs, 4 columnas de macOS en rojo); la ronda R13 es su respuesta |

## 5. Solicitud QA abierta (pendiente)

- **Solicitud:** dictamen de cierre del release CLI+MCP.
- **Sobre:** rama `work/release-cli-mcp-20261025` — **candidato de producto
  `015b776`** (`fix(R14)`: QA-R13-06 corregido + reconciliación y paquete de
  decisiones). Identidad completa en `audits/fase2/CANDIDATO-RELEASE.yaml`.
- **Estado de la ronda R14:** el P1 del dictamen `7dc1a25` (QA-R13-06) está
  corregido en causa — el cuerpo se consume UNA vez al llegar, con techo de
  1 MiB y plazo de 5 s; el 404 ya no re-drena; `payload_too_large` → 413;
  SP-04 intacto — con 4 regresiones nuevas HTTP crudas (L1 20/20, L2 121/121)
  y re-certificación integral: suite `r14` **6334/13/0**, puertas **26/26**,
  E2E **27/27**, y **CI 25/25 `completed/success`** en la corrida
  `40442954197` **del propio candidato** (el 25/25 de `e198ffb` no se
  reutiliza). Recibos del SHA: QG-03..QG-06 **PASS**; QG-00/QG-01 fallan solo
  por el reconciliador (10 divergencias sin ratificar) y QG-02 solo por la
  violación externa de `vault-backups` — política `liberable: false`
  (fail-closed, sin waiver). Para la decisión DEC-02, el plan B lleva ahora
  la identidad DIV-01..10, la **evidencia I2 medida** (el puerto propuesto no
  funciona fuera del checkout tal como está especificado) y el **coste
  medido** (§11.3: ~60× sin las enmiendas). Expedientes: buzón R14
  (`RESPUESTA-DEL-EJECUTOR.md`), matriz formal REL-00..13 (informe §10),
  `QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md`, `RECIBOS-R13-MANIFIESTO.md` y
  `RECIBOS-R14-MANIFIESTO.md`.
- **Base del dictamen anterior:** `7dc1a25` (rama
  `qa/review-release-cli-mcp-e198ffb-20261026`). Su hallazgo P1 queda
  respondido en la R14.
- Nombre candidato por convención: `qa/review-release-cli-mcp-015b776-20261027`.
- **Prerrequisitos que NO dependen de QA:** decisiones del propietario
  (divergencias A/B/C con el criterio §6.1 del plan B, política de QG-02,
  `vault-backups`), la Constitución arquitectónica y la matriz completa 25/25.
  Si siguen abiertas, el dictamen de cierre deberá declararlas `BLOCKED` con
  esas causas — que es el dictamen correcto.
