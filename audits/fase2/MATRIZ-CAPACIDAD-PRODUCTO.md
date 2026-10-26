# Matriz de capacidad del producto — qué se promete, qué hay, qué está probado

**Fecha de la medición:** 2026-10-26 · **Rama:** `work/release-cli-mcp-20261025`
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
| Entry point `vault` | ✅ `[project.scripts]` | ✅ `vault = vault.product_cli:main` | ✅ wheel | ✅ E2E (27/27) | Windows ✅ · Linux ✅ (CI) · macOS ❌ | `pyproject.toml`, E2E R11 | bajo |
| Comandos de producto (`init`, `doctor`, `status`, `tools`, `run`, `mcp-path`) | ✅ | ✅ | ✅ | ✅ E2E | idem | `vault/product_cli.py` | bajo |
| Comandos del toolkit (`groups`, `find`, `show`, `doctor`, `run`, `plan`, `batch`, `scan`) | ✅ Scope IN | ✅ (8 subcomandos en `python -m cli --help`) | ✅ | ⚠️ el E2E ejercita `run` y `doctor`; `plan`/`batch`/`scan` no están en el recorrido | idem | `python -m cli --help` (medido) | **medio**: superficie anunciada sin recorrido que la ejercite |
| Pre-vuelo: AP-36, anti-poison, `required_args` | ✅ | ✅ `cli/safety.py` | ✅ | ✅ E2E (contención) | idem | E2E + `tests/test_vault_containment.py` | bajo |
| `--verify-integrity` (hash antes/después) | ✅ Scope IN, ❌ DoD | ✅ presente en la CLI (`batch --verify-integrity`) | ✅ | ⚠️ **no ejercitado en el E2E** | idem | `python -m cli --help` | **medio**: el PRD lo marca pendiente y el código lo ofrece |
| Scheduler de olas / concurrencia | ✅ | ✅ `cli/scheduler.py` | ✅ | ⚠️ no ejercitado en el E2E | idem | `cli/scheduler.py` | **medio** |
| `--stop-on-error` en lote | ✅ | ✅ presente | ✅ | ⚠️ no ejercitado | idem | `cli/` | medio |
| `VAULT_TIMEOUT` / `--timeout` | ✅ | ✅ `--timeout` (CLI) y presupuesto en el registro de entorno | ✅ | ✅ (presupuesto medido por `test_o8_presupuesto`) | idem | `vault/kernel/entorno.py` | bajo |
| Salida JSON `{ok, tool, …}` | ✅ | ✅ | ✅ | ✅ E2E | idem | E2E | bajo |
| Códigos de salida 0/1/2/130 | ✅ | ✅ | ✅ | ⚠️ 130 (interrumpido) no medido | idem | `cli/runner.py` | bajo |
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
| macOS | implícito | ✅ | ✅ | ❌ **NOT_RUN**: los 8 jobs `macos-latest` no arrancan en la CI | ❌ | CI (jobs en cola) | **alto**: el estándar promete multi-plataforma y macOS no está medido |
| Instalación fuera del checkout | ✅ | ✅ | ✅ | ✅ venv externo en el E2E | idem | E2E | bajo |
| MCP empaquetado (sin checkout) | ✅ | ✅ `vault mcp-path` | ✅ | ✅ `tests/test_mcp_instalado.py` (8/8) | idem | idem | bajo |

## 5. Versión, canal de publicación y resumen para la decisión

### 5.1 Propuesta de versión y canal (no aplicada)

| Elemento | Propuesta | Por qué |
|---|---|---|
| Versión pública | **`41.24`** (la línea vigente; `41.23` es la instalada y publicada como base) | el producto sigue en la línea `v41.x` del manifiesto; saltar a `1.0.0` prometería una madurez que la matriz multiplataforma todavía no respalda (macOS sin medir) |
| Canal | **PyPI**, en un canal de prueba primero (TestPyPI o un índice propio), con el token del propietario | publicar en el canal público es una decisión suya, y un release sin QA de cierre no debe salir |
| Condición previa | **dictamen QA de cierre + QG-07 con CI concluida** (hoy, macOS) | el GOAL es explícito: CI fallida significa que el release no puede aprobarse |
| Qué NO se hace aquí | ni tag, ni `gh release`, ni `twine upload`, ni cambio de `version` en `pyproject.toml` | no hay autorización para publicar, y `vault_release_bump` existe para hacerlo con el proceso del repo |
| Si el propietario quiere `1.0.0` | entonces el PRD v1.0 se cumple, y el cambio de versión va por `vault_release_bump` con su changelog | el versionado público se cambia con la tool del repo, no a mano |

### 5.2 Resumen para la decisión de publicación

- **Publicable hoy, con Honestidad en el rótulo**: wheel + sdist, instalación
  limpia fuera del checkout, CLI de producto y MCP por JSON-RPC, en Windows
  (medido) y Linux (medido en CI). Es un **uso controlado por terceros
  técnicos**, no una distribución pública autorizada: no hay tag, ni release,
  ni dictamen QA de cierre, y las decisiones del propietario (divergencias,
  política de QG-02) siguen abiertas.
- **No publicable como multiplataforma**: macOS no tiene ni una sola
  medición. La CI lo demuestra con los 8 jobs `macos-latest` en cola.
- **La versión pública no se cambia aquí**: `41.23` es la vigente y cualquier
  tag o release exige la autorización que este GOAL no incluye.
