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

## 2. Autoridad de aceptación (fuente: `audits/fase2/catalogo-qg.yaml`)

| QG | Dueño | Aceptación |
|---|---|---|
| QG-00, QG-01, QG-03, QG-05, QG-06 | agente ejecutor | **QA arquitectónico** |
| QG-04 | agente ejecutor | **QA arquitectónico**; waiver solo con la divergencia documentada y aceptada por QA |
| QG-02 | agente ejecutor | **QA arquitectónico + propietario** |
| QG-07 (cierre) | propietario del producto | **QA arquitectónico (verifica) + propietario (autoriza)** |

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
| `qa/review-release-cli-mcp-29c1a15-20261025` | dictamen `a9e0143` (última revisión de release previa a esta ronda) |
| `qa/review-arquitectura-trazabilidad-e8f7aea-20261025` | **ACTIVA** — dictamen `9919c57` (8 hallazgos QA-ARC-01..08); la ronda R11 es su respuesta |

Ramas auxiliares históricas del ejecutor: `audit/archify-governance-20261024`
y `fase2/deuda-y-product-readiness-20261025` (cerradas; no participan en el
release actual).

## 5. Solicitud QA abierta (pendiente)

- **Solicitud:** dictamen de cierre del release CLI+MCP.
- **Sobre:** rama `work/release-cli-mcp-20261025` — **HEAD `ee7e64a`**, candidato
  congelado de producto `36c91e0` (suite 6307/0/0 y puertas 26/26 sobre ese
  mismo SHA; E2E 27/27 con wheel reconstruida sobre `0241ffe`, hashes en
  `audits/fase2/INFORME-READINESS-TERCEROS.md`).
- **Base del dictamen anterior:** `9919c57` — los 8 hallazgos QA-ARC están
  respondidos en la ronda R11 (estado por hallazgo en el informe y en el buzón).
- Nombre candidato por convención: `qa/review-release-cli-mcp-ee7e64a-20261026`.
- **Prerrequisitos que NO dependen de QA:** decisiones del propietario del
  informe §6 (divergencias A/B/C, contrato QG-02, CI). Si siguen abiertas, el
  dictamen de cierre deberá declararlas `BLOCKED` con esas causas — que es el
  dictamen correcto.
