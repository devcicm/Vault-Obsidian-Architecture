# Protocolo QA — agente, autoridad y ramas de trabajo

Referencia canónica de cómo opera el par QA ↔ ejecutor en este release. Fuente:
`INSTRUCCIONES-PARA-EJECUTOR.md` (órdenes), `audits/fase2/catalogo-qg.yaml`
(autoridad de aceptación) y los dictámenes del propio QA en `RESPUESTA-QA.md`.

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
  `e198ffb`** (código de `9c65401` más el drenaje del cuerpo en el rechazo
  del servicio de tokens y la documentación de la ronda; el único commit que
  sigue es documental, el que publica este protocolo actualizado).
- **Estado de la ronda R13:** los seis defectos de la ronda corregidos, cada
  uno con su causa comprobada y su regresión: el lock que moría con EINVAL en
  macOS (R13-03a), el escáner legacy cuyo recuento dependía del orden del
  sistema de ficheros porque la propia pasada creaba los ficheros que contaba
  (R13-02), el servicio de tokens sin diagnóstico de arranque y con carrera de
  puerto (R13-01), la copia del sandbox vivo cogida en mitad en Windows 3.10
  (R13-03b), la clasificación de CI que llamaba «pendiente» a una corrida ya
  concluida en rojo (R13-04) y el rechazo de SP-04 que en Windows 3.10 cortaba
  la conexión a RST porque mandaba el 403 sin leer el cuerpo (R13-05). La
  corrida de verificación del fix, `40420024458`, dejó **24 de 25** — y la
  corrida final, `40430269201` **sobre el candidato `e198ffb`, es 25/25:
  `completed/success` con las cuatro columnas de macOS en verde** por primera
  vez. Detalle y evidencia:
  `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` (ronda R13),
  `audits/fase2/CI-diagnostico.md` (reesrito con las fichas D1–D10 +
  R13-01..05) y `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` (criterio de
  independencia semántica y operacional añadido §6.1).
- **Base del dictamen anterior:** `e30e668` (rama
  `qa/review-release-cli-mcp-408eb23-20261026`). Los hallazgos quedan
  respondidos en la R13.
- Nombre candidato por convención: se publica con el buzón R13.
- **Prerrequisitos que NO dependen de QA:** decisiones del propietario
  (divergencias A/B/C con el criterio §6.1 del plan B, política de QG-02,
  `vault-backups`), la Constitución arquitectónica y la matriz completa 25/25.
  Si siguen abiertas, el dictamen de cierre deberá declararlas `BLOCKED` con
  esas causas — que es el dictamen correcto.
