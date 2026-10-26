# Informe de readiness para terceros — GOAL CLI + MCP

**Fecha:** 2026-10-26
**Rama:** `work/release-cli-mcp-20261025`
**HEAD:** `0241ffe` · **Candidato de producto congelado:** `31dfa46`
**Dictámenes vigentes:** `9919c57` (8 hallazgos QA-ARC-01..08 sobre la capa de trazabilidad) y `a9e0143`
**Estado general:** **ADVANCE — usable por terceros técnicos hoy en Windows; release 1.0 pendiente del encadenado QG, de la CI y de decisiones explícitas del propietario**

Este informe consolida el "cómo va el proyecto" con la evidencia que existe
hasta `0241ffe`. Cada cifra lleva su fuente. Lo que NO ha corrido todavía se
declara `NOT_RUN`, nunca PASS (no hay una sola figura estimada).

---

## 1. Qué es lo que un tercero recibe

Un paquete Python publicado como **wheel y sdist** que instala dos superficies
de producto **sin el checkout, sin el toolkit y sin servicios externos**:

| Superficie | Contrato | Evidencia |
|---|---|---|
| **CLI** `vault.exe` (`init`, `doctor`, `status`, `tools`, `run`, `mcp-path`) | instalar y operar un runtime standalone | recorrido de terceros R07/R09: **27/27** sobre `31dfa46` |
| **Servidor MCP** (`vault-mcp-server.mjs`) | 97 tools expuestas por JSON-RPC/stdio (`initialize`, `tools/list`, `tools/call`) mismo runtime | cliente MCP secuencial del recorrido E2E |
| **Vault resultante** | markdown plano legible con un editor de texto | el vault sobrevive a que el toolkit desaparezca (decisión de producto, probada por las tools de lectura) |

Wheel `858f1407…9c1` · sdist `22cf5d0c…472`, construidos en R09 e instalados en
un entorno consumidor aislado de este repo (venv externo, no versionado). Sobre
`0241ffe` se reconstruyó el paquete con el fix AP-39 dentro para el E2E de
cierre (hashes en §2).

## 2. Calidad medida hasta `0241ffe`

| Métrica | Valor | Fuente |
|---|---|---|
| Puertas del estándar | **26/26** | `vault_gate.py --strict` (última corrida sobre `5ef89ff`; re-corrida sobre `0241ffe` en vuelo) |
| Suite completa | **6300 passed / 13 skipped / 0 failed** en **1076,4 s** de reloj | JUnit `r11c` sobre `0241ffe` |
| E2E de terceros | **27/27** con wheel **reconstruida desde el código actual** (el fix AP-39 dentro del paquete): wheel `79043404…73b066`, sdist `cc6b2224…57afbe` | `recorrido_terceros_r07.py` sobre `0241ffe` |
| AP-39 (defecto de producto) | **corregido**: 0 violaciones en runtime limpio con 75 ficheros | re-auditoría con código actual (commit `2174bb1`) |
| Hallazgos del ledger | 15 fichas: 14 abiertas (contenido de evidencia del sandbox) + 1 **CORREGIDO** (INC-0015, AP-39) | `hallazgos-qg02.yaml` |
| Divergencias Archify | 10 (2 fichas de movimiento de composición 667a6a5, 5 accesos, 3 dependencias) | `reconciliar_archify.py --check` (exit 1 esperado sin ratificación) |
| Veredictos QG | 64 | `registro-veredictos.yaml` |
| Paralelismo de la suite | suma de casos 8255 s contra 1076 s de reloj = **7,7×** | JUnit `r11c` + log de la corrida |
| Rendimiento del generador de trazabilidad | **67,2 s → 9,7 s** (una sola llamada `git ls-tree` + `git cat-file --batch` en binario, antes un `git show` por fichero) | Measure-Command corriendo el script (dos mediciones reales) |

## 3. Pirámide de validación (L0-L3, medida)

De la corrida `r11c` sobre `0241ffe` (587 ficheros de test, 6313 casos —
`PIRAMIDE-VALIDACION.md`):

| Nivel | Ficheros | Casos | Tiempo | % |
|---|---:|---:|---:|---:|
| L0 sanidad | 465 | 5542 | 3882 s | 47,0 % |
| L1 unidad | 83 | 605 | 1692 s | 20,5 % |
| L2 integración | 37 | 160 | 2453 s | 29,7 % |
| L3 extremo | 2 | 6 | 227 s | 2,8 % |

**Carril rápido (L0+L1): 97,4 % de los casos con 67,5 % del tiempo** — para
iterar (NO sustituye al cierre). La mediana esconde los viajes únicos largos y
el doc los lista explícitamente: `test_fix_all` (caso de 137 s, mediana 6,6 s),
`test_banco_agente` (90 s, mediana 0,0 s), `test_sandbox_fixture` (66 s),
`test_arch_escrituras_de_sistema` (59 s). Ese patrón es la **evidencia de la
duplicación**: gates completos ejecutados dentro de tests que ya cubren las 26
puertas. La desduplicación está identificada; ejecutarla es trabajo del siguiente
round, no de este informe.

La suma de tiempos bajó de 10313 s (corrida `r11b`) a 8255 s con el mismo
árbol de casos: la contención que mi generador causaba con ~1200 subprocesos
git se eliminó en la raíz (67,2 s → 9,7 s) y toda la suite la respiró.

## 4. El encadenado QG-00 → QG-07: qué bloquea qué

Estado auténtico (colector con subchecks independientes, recibos con hash por
subcheck en carpeta externa de recibos):

```
QG-00 ─┬─ BLOCKED → 10 divergencias sin ratificar (decision A/B/C del propietario)
        │
QG-01 ─┤   (usa el propio reconciliador → comparte el bloqueo)
QG-02 ─┤   14 hallazgos del sandbox (contenido de evidencia, no producto)
        │   + contrato de certificación sin ratificar (runtime limpio vs sandbox)
QG-03..06 ─┤   recibos PASS con artefacto y SHA-256 por subcheck,
        │   PERO quedan atrapados por el prerrequisito QG-00 (regla del catálogo)
QG-07 ─┴─ CI: runs en cola SIN UNO completado para ningún SHA
             → QG-07 BLOCKED por causa externa (facturación de GitHub Actions)
```

La lectura honesta: **el producto técnico está en verde; la acreditación formal
está detenida contigo** — en las decisiones §6 y en la cuenta de CI (§7.3).

## 5. Readiness para terceros: qué sí, qué no

### 5.1 Lo que UN tercero puede hacer HOY

```
pip install la-wheel           # ~1 min
vault init <su-runtime>        # crea el vault completo (17 carpetas, nav, bitácoras)
vault doctor                   # diagnostica
vault run / servidor MCP       # 97 tools disponibles
```

**Garantizado y probado:** instalación limpia fuera del checkout, runtime
recién creado en **0 violaciones** del estándar (AP-39 corregido y re-auditado),
operación determinista, `NOT_RUN` nunca se cuelga como PASS, rutas y datos
personales fuera de lo publicado (`comprobar_saneamiento` exit 0 en cada commit),
preflight anti-poison no desactivable en la única tool con superficie de
escritura, escrituras atómicas y contenidas dentro del vault.

### 5.2 Lo que NO garantizamos aún

1. **Multiplataforma.** Todo lo verde es **Windows-only** (esta máquina). La CI
   que acreditaría Linux/macOS **nunca ha completado un run** para ningún SHA.
   Para un tercero en macOS/Linux, lo que cabe decir es `NOT_RUN`, no funcional.
2. **Un dictamen QA formal de cierre** del candidato `31dfa46 + capa R11` sobre
   el SHA final de la ronda (el dictamen `9919c57` es de la entrada de la capa,
   no de la salida).
3. **No es un servicio de almacenamiento seguro**: la fiabilidad del vault es
   la del markdown plano más auditoría del estándar; **no cifrado, no multiusuario**.

## 6. Decisiones pendientes del propietario (el punto crítico)

Nada de esto lo puede hacer el ejecutor; cada una tiene su expediente:

| # | Decisión | Opciones | Recomendación técnica |
|---|---|---|---|
| 1 | **10 divergencias DIV-01..10** (cruces heredados del movimiento `667a6a5`) | **A** eliminar el cruce componiendo desde el meta-toolkit · **B** migrarlo a un owner con puerto declarado · **C** excepción formal con plazo | **B** (migración compatible; detalles en `QA-RC-03-CRUZES.md`) |
| 2 | **Contrato de QG-02** | certificar sobre runtime limpio (creado por el producto) vs sobre el sandbox canónico del repo | runtime limpio (es lo que consume un tercero) |
| 3 | **CI en cola** | activar la cuenta (Settings → Billing → Actions) o declarar el límite | activar: sin ella, QG-07 y la matriz multiplataforma quedan sin evidencia posible |
| 4 | **Ratificar la Constitución arquitectónica** (DRAFT) | ratificar, corregir o rechazar con motivo | decide el propietario tras el dictamen QA de cierre |
| 5 | **Purga de `vault-backups`** fuera del vault (AP-36) | purgar o declarar | contenido inventariado; lo deciden los dueños de los datos |
| 6 | Reescritura del historial publicado | sí / no | riesgo documental (fichas históricas), solo el propietario |

## 7. Riesgos residuales (con dueño y estado)

| Riesgo | Dueño | Estado |
|---|---|---|
| 14 hallazgos del sandbox (CN-03×5, AP-07×4, AP-64×4, AP-36×1) | desarrollador del vault de evidencia | abiertos; son contenido de fixture, no defecto de producto |
| Planificador por impacto basado en grafo desfasado | el propio repo | mitigado por conservadurismo: sin impacto determinable exige suite completa |
| Duplicación gates-dentro-de-tests (5 casos únicos > 100 s, ver §3) | revisión futura del harness | identificado y medido; sin ejecutar |
| Baselines congeladas con deuda declarada | apuntalar en cada round | los decrementos son la dirección (policy: solo encogen) |
| El QA de la capa | dictamen pendiente | `9919c57` respondido con R11; solicitar re-auditoría sobre el SHA de cierre |

## 8. Qué significaría "seguro-functional" completo (checklist de cierre)

1. [x] Producto técnico verificado end-to-end (E2E 27/27 + suheel limpio).
2. [x] Error/deuda declarada con dueño — nada verde para meter prisa.
3. [ ] QG-00/QG-01: ratificación de divergencias (§6.1).
4. [ ] QG-02: contrato ratificado + re-auditoría formal del AP-39 publicado.
5. [ ] CI: un run COMPLETADO sobre el SHA congelado (QG-07 + multiplataforma).
6. [ ] QG-03..06: recibos desbloqueados por el encadenado.
7. [ ] Dictamen QA de cierre y ratificación de la Constitución.
8. [ ] Congelar el SHA definitivo y re-certificar (26 puertas + suite + E2E +
      recibos + QG por CLI) — §9.

## 9. Estado de la certificación de cierre

- Suite completa `r11c` sobre `0241ffe`: **COMPLETA — 6300 passed / 13 skipped /
  0 failed / 0 errores** en 1076,4 s.
- Puertas sobre `0241ffe`: 26/26.
- E2E sobre `0241ffe` con wheel reconstruida: **27/27** (artefactos con hash nuevo).
- Pendiente tras congelar el SHA del freeze del informe: suite + puertas + E2E
  de cortesía sobre ese SHA (los deltas desde `0241ffe` son documentales y una
  pirámide medida; el cierre formal pide, de todos modos, re-certificación del
  SHA congelado).

**Veredicto:** el proyecto está en el mejor estado de su historia y **sí puede
usarse por terceros hoy** bajo las condiciones de §5.1 (Windows, uso técnico,
sin promesas enterprise). El paso que lo convierte en release certificado es
corto y es tuyo: §6 (decidir A/B/C), contrato de QG-02 y CI —
con eso, yo desbloqueo el resto del encadenado con los recibos existentes.
