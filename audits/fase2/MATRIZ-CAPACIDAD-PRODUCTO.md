# Matriz de capacidad del producto — qué se promete, qué hay, qué está probado

**Estado vigente (R15, 2026-10-27):** candidato `015b7765b80cac21c6dcf859ae075d036cd01def`, CI 25/25
(`40442954197`). **macOS está medido**; las filas de superficie `python -m cli`
fueron reclasificadas como NO empaquetadas (QA-R14-PORT-01). El corte anterior
(2026-10-26) queda como histórico en el git de este fichero.

### Clasificación de alcance del release (GOAL R16 §11)

| Capacidad | Etiqueta | Base |
|---|---|---|
| CLI de producto (`init`, `doctor`, `status`, `tools`, `run`, `mcp-path`) | `SHIPPED_AND_TESTED` | E2E 27/27 + CI 12 columnas |
| MCP stdio JSON-RPC (97 tools + 7 recursos `vault://`) | `SHIPPED_AND_TESTED` | E2E + `test_mcp_runner` + `test_mcp_recursos` |
| Runtime standalone + persistencia + cuarentena/restore | `SHIPPED_AND_TESTED` | E2E + `test_vault_init_clean` |
| SP-04 del servicio de tokens | `SHIPPED_AND_TESTED` | 20/20 con los 5 criterios del dictamen |
| SSE/HTTP (`--port` del servidor MCP) | `SHIPPED_NOT_TESTED` | único `NOT_RUN` de la superficie distribuida: declarado, sin prueba |
| `python -m cli` (`groups/find/show/doctor/run/plan/batch/scan`) | `NOT_SHIPPED` | el paquete `cli/` no viaja en la wheel (verificado) |
| `--verify-integrity`, scheduler de olas, `--stop-on-error`, salida 130 | `NOT_SHIPPED` | ídem (superficie de mantenimiento del checkout) |
| Superficie de mantenimiento (`vault_norms --audit`, gates, audits) | `NOT_SHIPPED` | `installed: false` en la wheel; propia del checkout |
| Quick Start «checkout» del README (TD-0009/DOC-0001) | `OUT_OF_SCOPE` (canal wheel) | corregir la documentación, no el paquete |
| Tools retiradas (`vault_backup_base64`, `vault_restore_base64`) | `DEPRECATED` | superseded_by en el catálogo |

Ninguna capacidad `SHIPPED_NOT_TESTED` se anuncia como certificada: si el
propietario quiere incorporar SSE/HTTP al canal, el incremento exige su
recorrido E2E + impacto en QG-03/05/06/07 y un nuevo candidato.

**Fecha de la medición base:** 2026-10-26 · **Rama:** `work/release-cli-mcp-20261025`
**Cómo se mide:** cada fila dice de dónde sale el dato. Lo que no se ha ejecutado
figura `NOT_RUN`; lo que existe en el código pero no se ha ejercitado figura
`implementado, no probado`. Ninguna fila se completa con una cifra del PRD.

Las fuentes de esta matriz, todas en este repo:

| Documento | Papel | Fecha |
|---|---|---|
| `docs/product/prd-cli.md` | PRD de la CLI (**target v1.0**, 2026-09-20) | desactualizado en cifras |
| `docs/product/prd-mcp.md` | PRD del servidor MCP (**target v1.0**, 2026-09-20) | desactualizado en cifras |
| `pyproject.toml` | versión y piso de Python (fuente) | `41.23`, `>=3.9` |
| `mcp/nodejs/tools-catalog.json` | catálogo publicado (derivado) | 126 tools |
| `cli/README.md`, `cli/COMMANDS.md` | referencia de la CLI | vigente |
| `audits/fase2/INFORME-READINESS-TERCEROS.md` | estado de la certificación | se actualiza en esta ronda |

## 1. Corrección de partida: las cifras del PRD están caducadas

| Afirmación del PRD | Medido (2026-10-26) | Fuente de la medición |
|---|---|---|
| MCP «expone 116 tools» (visión) y «117 tools» (promesa) | **126** en el catálogo; **97** expuestas por `tools/list`; **14** con el perfil `agente` | `tools-catalog.json` (126) + sesión JSON-RPC real (`tools/list` → 97; `VAULT_MCP_PERFIL=agente` → 14) |
| MCP «9 tools JS-native» | **2** | `tools-catalog.json` → `js_native_tools` |
| PRD CLI «target v1.0» | versión instalada **41.23** | `pyproject.toml` |

Las 97 no son 126 menos 29 por capricho: 29 tools están retiradas de MCP a
propósito (`exposed_via_mcp: false`), y el resto de la diferencia entre 126 y
97 es exactamente esa retirada. El número que un agente ve es 97; el que el
catálogo publica es 126.

## 2. Matriz CLI

| Capacidad | DECLARADA (PRD) | IMPLEMENTADA | EMPAQUETADA | PROBADA | SOPORTADA | EVIDENCIA | RIESGO |
|---|---|---|---|---|---|---|---|
| Entry point `vault` | ✅ `[project.scripts]` | ✅ `vault = vault.product_cli:main` | ✅ wheel | ✅ E2E (27/27) | Windows ✅ · Linux ✅ · macOS ✅ (CI 25/25, corrida `40442954197`) | `pyproject.toml`, E2E, CI | bajo |
| Comandos de producto (`init`, `doctor`, `status`, `tools`, `run`, `mcp-path`) | ✅ | ✅ | ✅ | ✅ E2E | idem | `vault/product_cli.py` | bajo |
| Comandos del toolkit (`groups`, `find`, `show`, `doctor`, `run`, `plan`, `batch`, `scan`) | ✅ Scope IN | ✅ (8 subcomandos en `python -m cli --help`) | ❌ **NO empaquetada**: `python -m cli` no existe en site-packages (verificado 2026-10-27 contra la wheel del candidato; el paquete `cli/` no viaja) | ✅ en el checkout (`run`, `doctor`); el resto sin recorrido | **fuera del alcance del producto distribuido**: superficie de mantenimiento del checkout, no del paquete | `cli/vault_cli.py`; listing de site-packages | **corregido (QA-R14-PORT-01)**: el PRD la anunciaba como empaquetada |
| Pre-vuelo: AP-36, anti-poison, `required_args` | ✅ | ✅ `cli/safety.py` | ✅ | ✅ E2E (contención) | idem | E2E + `tests/test_vault_containment.py` | bajo |
| `--verify-integrity` (hash antes/después) | ✅ Scope IN, ❌ DoD | ✅ presente en la CLI (`batch --verify-integrity`) | ❌ **NO empaquetada** (misma razón: `cli/` no viaja en la wheel) | ⚠️ no ejercitado | fuera del alcance del producto distribuido | `cli/vault_cli.py` | **corregido**: no bloquea el release |
| Scheduler de olas / concurrencia | ✅ | ✅ `cli/scheduler.py` | ❌ **NO empaquetada** | ⚠️ no ejercitado | fuera del alcance del producto distribuido | `cli/scheduler.py` | **corregido** |
| `--stop-on-error` en lote | ✅ | ✅ presente | ❌ **NO empaquetada** | ⚠️ no ejercitado | fuera del alcance del producto distribuido | `cli/` | **corregido** |
| `VAULT_TIMEOUT` / `--timeout` | ✅ | ✅ `--timeout` (CLI) y presupuesto en el registro de entorno | ✅ | ✅ (presupuesto medido por `test_o8_presupuesto`) | idem | `vault/kernel/entorno.py` | bajo |
| Salida JSON `{ok, tool, …}` | ✅ | ✅ | ✅ | ✅ E2E | idem | E2E | bajo |
| Códigos de salida 0/1/2/130 | 0/1/2 ✅ · 130 ✅ (CLI del toolkit) | ✅ | 0/1/2 ✅ en la wheel · 130 ❌ (vive en `cli/runner.py`, no empaquetado) | ✅ 0/1/2 E2E · ⚠️ 130 no medido (y fuera del paquete) | 0/1/2 ✅ · 130 fuera del alcance del producto distribuido | `cli/runner.py`, `vault/product_cli.py` | **corregido**: el 130 no es superficie del paquete |
| Sin dependencias fuera de stdlib + PyYAML | ✅ | ✅ | ✅ `PyYAML` declarado | ✅ | idem | `pyproject.toml` | bajo |

## 3. Matriz MCP

| Capacidad | DECLARADA (PRD) | IMPLEMENTADA | EMPAQUETADA | PROBADA | SOPORTADA | EVIDENCIA | RIESGO |
|---|---|---|---|---|---|---|---|
| JSON-RPC 2.0 sobre stdio | ✅ | ✅ | ✅ `vault_toolkit/mcp/` | ✅ sesión real | idem | `tests/test_mcp_runner.py` (9/9) | bajo |
| SSE/HTTP | ✅ | ✅ (`--port`) | ✅ | ❌ **NOT_RUN** | ❌ | `vault-mcp-server.mjs` | **medio**: superficie declarada y sin prueba |
| `tools/list` | ✅ | ✅ | ✅ | ✅ | idem | sesión real (97) | bajo |
| `tools/call` (cualquier tool del catálogo) | ✅ | ✅ | ✅ | ✅ (97 expuestas; AP-42 ejecuta el ejemplo de cada una) | idem | E2E + gate `toolkit_audit` | bajo |
| `resources/list` + `resources/read` | ✅ Scope IN, ❌ DoD | ✅ (7 recursos) | ✅ | ✅ **nuevo en esta ronda** | idem | `tests/test_mcp_recursos.py` (9/9) | bajo (estaba roto: `vault://graph` devolvía el error dentro del texto) |
| Guard chain: secret scan, brackets, Mermaid, content gate | ✅ | ✅ | ✅ | ✅ | idem | `tests/test_mcp_runner.py` | bajo |
| Tools JS-native | ✅ «9» | ✅ **2** | ✅ | ✅ | idem | `tools-catalog.json` | bajo (el PRD exageraba) |
| `VAULT_SCAN_ROOTS` (multi-vault) | ✅ | ✅ | ✅ | ✅ | idem | `test_mcp_runner.py` (acota el barrido) | bajo |
| Trace log de ejecuciones | ✅ | ✅ | ✅ | ✅ | idem | `vault://traceability/mutations` | bajo |
| `VAULT_MCP_PYTHON` (intérprete del toolkit) | ✅ implícito | ✅ (detección con sondeo de PyYAML desde R12) | ✅ | ✅ | idem | `mcp/nodejs/vault-mcp-server.mjs` | **alto antes de R12**: elegía `py` y en Windows resolvía un intérprete sin PyYAML → todas las tools caían |

## 4. Matriz de versionado, instalación y plataformas

| Capacidad | DECLARADA | IMPLEMENTADA | EMPAQUETADA | PROBADA | SOPORTADA | EVIDENCIA | RIESGO |
|---|---|---|---|---|---|---|---|
| Versión pública | `41.23` (`pyproject.toml`) | ✅ | ✅ | ✅ `vault --version` | idem | `pyproject.toml`, `test_version_coherence.py` | bajo |
| Canal de publicación | — | wheel + sdist (`python -m build`) | ✅ | ✅ E2E desde la wheel | ⚠️ **sin publicar**: no hay tag ni release, y no los habrá sin autorización del propietario | E2E R11 (hashes) | medio |
| Piso de Python | `>=3.9` | ✅ | ✅ | ✅ matriz CI 3.9–3.12 | 3.9–3.12 ✅ · 3.14 ✅ local | `pyproject.toml`, `tests/test_piso_python.py` | bajo |
| Windows | implícito | ✅ | ✅ | ✅ suite + E2E locales, y CI | ✅ | E2E, CI | bajo |
| Linux | implícito | ✅ | ✅ | ✅ CI (jobs `ubuntu-latest` verdes en la corrida medida) | ✅ | CI | bajo |
| macOS | implícito | ✅ | ✅ | ✅ **CI_PASS**: las 4 columnas `macos-latest` en verde en la corrida `40442954197` del candidato `015b776` (12 `Validate` + 12 `Product gates` + Lint = 25/25) | ✅ | CI | **resuelto**: la matriz multiplataforma está medida (antes `NOT_RUN`, historia en `CI-diagnostico.md`) |
| Instalación fuera del checkout | ✅ | ✅ | ✅ | ✅ venv externo en el E2E | idem | E2E | bajo |
| MCP empaquetado (sin checkout) | ✅ | ✅ `vault mcp-path` | ✅ | ✅ `tests/test_mcp_instalado.py` (8/8) | idem | idem | bajo |

## 5. Versión, canal de publicación y resumen para la decisión

### 5.1 Propuesta de versión y canal (no aplicada)

| Elemento | Propuesta | Por qué |
|---|---|---|
| Versión pública | **`41.24`** (la línea vigente; `41.23` es la instalada y publicada como base) | el producto sigue en la línea `v41.x` del manifiesto; saltar a `1.0.0` prometería una madurez que las decisiones de gobernanza pendientes (DEC-01..06) todavía no respaldan |
| Canal | **PyPI**, en un canal de prueba primero (TestPyPI o un índice propio), con el token del propietario | publicar en el canal público es una decisión suya, y un release sin QA de cierre no debe salir |
| Condición previa | **dictamen QA de cierre + QG-00..QG-07 en PASS efectivos + autorización del propietario** (la CI ya está: 25/25 del candidato) | el GOAL es explícito: CI aprobada no es autorización de publicación |
| Qué NO se hace aquí | ni tag, ni `gh release`, ni `twine upload`, ni cambio de `version` en `pyproject.toml` | no hay autorización para publicar, y `vault_release_bump` existe para hacerlo con el proceso del repo |
| Si el propietario quiere `1.0.0` | entonces el PRD v1.0 se cumple, y el cambio de versión va por `vault_release_bump` con su changelog | el versionado público se cambia con la tool del repo, no a mano |

### 5.2 Resumen para la decisión de publicación

- **Publicable hoy, con Honestidad en el rótulo**: wheel + sdist, instalación
  limpia fuera del checkout, CLI de producto y MCP por JSON-RPC, **medidos en
  las tres plataformas** (Windows, Linux y macOS: corrida `40442954197`,
  25/25). Es un **uso controlado por terceros técnicos**, no una distribución
  pública autorizada: no hay tag, ni release, ni dictamen QA de cierre, y las
  decisiones del propietario (divergencias, política de QG-02) siguen
  abiertas.
- **Alcance explícito (QA-R14-PORT-01)**: la superficie distribuida es el CLI
  de producto + MCP stdio. La superficie `python -m cli` (con `plan`,
  `batch`, `--verify-integrity`, scheduler y el código de salida 130) **no
  viaja en la wheel**: es superficie de mantenimiento del checkout y queda
  FUERA del alcance del release (corregido en §2-3; el PRD la anunciaba como
  empaquetada). El único `NOT_RUN` de la superficie distribuida es
  **SSE/HTTP** (`--port` del servidor MCP): declarado, sin prueba.
- **La versión pública no se cambia aquí**: `41.23` es la vigente y cualquier
  tag o release exige la autorización que este GOAL no incluye.
