# Estudio del vault `vault dev codex` y plan de soluciones — 2026-10-30

**Qué es esto.** Lectura (solo lectura, vía MCP) de las 190 notas del vault de otro entorno
que analizó este repo, más un plan ordenado y la propuesta de qué tools exponer por MCP.
**No es dictamen QA** ni cambia el código. Nada de lo de abajo está aplicado.

## 1. Cómo se leyó y qué tan fiable es

| Dato | Valor |
|---|---|
| Servidor | `https://10.10.10.5:3000`, `vault-mcp-server` v41.25, certificado fijado (sin `-k`) |
| Notas volcadas | 190 de 190 (`vault_list` + `vault_read`, 0 fallos); ninguna escritura |
| Composición | 41 `19_Audits`, 27 `11_Code` (20 stubs), 18 `18_Bugs`, 14 `15_Tests`, 10 `21_QA`, resto secciones del estándar |
| Estado de las notas | 73 draft, 42 stub, 18 template, 16 in-progress, 41 sin estado (índices generados) |
| Lectura completa | consolidado de remediación, parity CLI/MCP, readiness de red MCP, gaps del vault, registro de riesgos, propuestas QA, evaluación crítica, propuestas CRUD y ciencia de datos |
| Lectura por resumen | índices y stubs generados (~90 notas), y las notas de `11_Code`/`18_Bugs` a través de su tabla en el consolidado |

**Base de las mediciones:** las hizo otro agente (`opencode`) sobre `e3cc1856`. `main` está hoy en
`09b2f6d`, así que son **afirmaciones por revalidar**, no hechos. Cotejé 5 contra `main` actual:

| Hallazgo | Estado en `main` (09b2f6d) |
|---|---|
| A-21 «83 normas (44 AP+6+3+3)», rango AP-01..44 | **Sigue** (manifiesto línea 3601) |
| A-14 ejemplo `total: 76 / groups: 35` | **Sigue** (`cli/COMMANDS.md:51`) |
| B-03 CI sin disparador por tags | **Sigue** (`vault-ci.yml`: solo push/PR a main/master) |
| A-12 `SKILLS.md` manda `export VAULT_ROOT=$(pwd)` | **Sigue** (`docs/SKILLS.md:223`) |
| A-11 `escritura_admitida` admite raíz explícita | **Sigue**: `if confiada or VAULT_PERMISSIVE_ROOT: return True` |

El resto (A-01…A-10, B-01, B-02, D-*) no lo reproduje; hay que hacerlo por fix con su test que falle primero.

## 2. Lo que dicen las notas, condensado

El vault es un análisis del estándar hecho desde fuera (regla 7). Produce **39 ítems** en cuatro grupos:

- **A, código del repo (22):** instalador/desinstalador devuelven 0 tras fallar (A-01); gates de contrato sin envelope (A-02);
  `merkle_de` descarta ficheros ilegibles y `verificar` da `ok` siempre (A-07); `TOOL_TIMEOUT` miente sobre «terminada» (A-06);
  RC-01 se suprime con un comentario (A-08); AP-13 no detecta timestamps inválidos (A-05); slug truncado deja `-` final (A-04);
  vocabulario `ESTADOS` copiado en 3 sitios (A-16); manifiesto con numeración de grupos y cifras de normas desalineadas (A-17..A-22).
- **B, release (6):** **B-01 crítico**, la puerta de publicación lee `release_authorized` y nunca `qg_statuses`/`qa_verdict_ref`;
  **B-02 crítico**, ata por ancestría, no por contenido (`product_tree_sha` existe y no se lee); B-03 CI sin tags; B-04 colector fuera de toda puerta;
  B-05 referencias QA/propietario aceptan cualquier string; B-06 decisión del propietario (política A/B/C).
- **C, contenido del vault (12):** 5 de 7 derivados faltan (`vault_doc_staleness` rojo, adrede, para conservar una reproducción);
  `VAULT-PURPOSE.md` en la raíz no se indexa; ADRs retroactivos en `03_Decisions`; 20 stubs en `11_Code`; secciones vacías.
- **D, objetivos como notas (7):** `id`/`createdAt` sin penalización (D-01); campos `superseded_by`, `requirement_state`… no declarados (D-02);
  el vault registra que cambió un fichero, no un objetivo (D-03); `vault_move`/`vault_delete` no actualizan los 6 índices de dominio,
  **2 de 14 entradas de `.bugs-index.json` apuntan a rutas inexistentes** (D-04); sin `--list` de requisitos (D-05).
- **Seguridad MCP (en parity/readiness):** `assertWithinVault` es léxico; `vault_restore_base64` podría salir por symlink/junction
  (hipótesis, no reproducida); `ok:true` con `exit_code≠0` en gates; sin granularidad de permisos por tool.

## 3. Plan de soluciones

Regla del plan: cada ítem entra con **un test que falle contra el código actual**, ciclo `síntoma → norma → guard → test` (AGENTS.md reglas 3-5),
sin baseline nueva, sin tool nueva. Todo en `main`, nada de push sin su orden.

| Fase | Ítems | Por qué ahí | Aceptación |
|---|---|---|---|
| 0. Revalidar | los 39 sobre `09b2f6d` | Las mediciones son de `e3cc185`; no inferir arreglos de un título de commit | Cada ítem: reproduce / ya corregido / no reproduce, con SHA |
| 1. Honestidad de los gates | A-02, B-01 | Un gate que no reporta o que acepta todo invalida el resto. B-01 es lo único crítico y solo lee campos que el manifiesto ya trae | Spec-less → envelope `FILE_NOT_FOUND`; la matriz de 12 casos del release rechaza lo que debe |
| 2. Integridad de datos | A-07, A-01, D-04, A-06 | Únicos que dicen `ok`/0 sobre corrupción, borran lo ajeno o dejan índices huérfanos | Backup con fichero ilegible ⇒ incompleto; instalador con paso fallido ⇒ exit 1; 0 entradas fantasma tras mover |
| 3. Release atado al contenido | B-02, B-05, B-04, B-03 | B-02 necesita el delta declarado antes; B-03 es lo más caro y B-02 ya cierra el hueco | Tag cuyo árbol difiere de `product_tree_sha` fuera de delta ⇒ rechazado |
| 4. Seguridad MCP | symlink/junction en restore, A-10, perfiles (sección 4) | Antes de abrir el MCP a más clientes que el LAN propio | Test en raíz desechable: ninguna lectura/escritura fuera de la raíz |
| 5. Normas y vocabulario | A-05, A-16, A-04, A-08, A-09, A-11, A-12 | Medios, independientes y pequeños | Un fixture por forma inválida; `ESTADOS` en un solo sitio |
| 6. Manifiesto | A-17…A-22, A-14, A-19 | Un solo documento, cinco defectos | Cifras que suman; 37 grupos con encabezado; las 4 tools faltantes documentadas |
| 7. Vault dev codex (contenido) | C-01…C-12, D-01…D-03, D-05…D-07 | Es trabajo de contenido, no de código; C-08 es una sola orden pero **destruye la reproducción**: decidir antes | Regenerar solo en copia; `vault_doc_staleness --check --strict` verde en la copia |

Decisiones tuyas (no mías): **B-06** (política A/B/C), si el vault vivo conserva la reproducción de derivados ausentes (C-08),
y el idioma por sección (R4). Lo que ya está resuelto: **H-1** (`09b2f6d`) cubre el equivalente en el repo, no en el vault consumidor.

## 4. Qué tools exponer por MCP

**Hallazgo que cierra una duda.** `tools_loaded: 127` vs `tools/list: 97` **no es un fallo**: `tools-catalog.json` marca
`exposed_via_mcp: false` en exactamente 30 tools y el servidor las filtra al listar (`vault-mcp-server.mjs:1012`) y al ejecutar (`:1134`).
Hay además un mecanismo de perfiles (`VAULT_MCP_PERFIL`, `perfiles.agente` = 14 tools) que hoy no se usa en el servidor remoto.

### 4.1 Las 30 no expuestas: mantenerlas fuera (con 3 matices)

Son el meta-toolkit de gobernanza **del estándar** (AGENTS.md: «no tocan las notas de nadie»): `vault_gate`, `vault_arch`, `vault_blueprint`,
`vault_changelog_check`, `vault_ciclos`, `vault_clones`, `vault_criterios`, `vault_doc_counts`, `vault_doc_sync`, `vault_error_contract`,
`vault_esquema`, `vault_excepcion_declarada`, `vault_kernel`, `vault_metricas`, `vault_noop_audit`, `vault_blame_audit`, `vault_norms_coherence`,
`vault_procesos_git`, `vault_produccion`, `vault_recursos`, `vault_servicio`, `vault_smoke`, `vault_toolkit_audit`, `vault_voice`,
más `vault_fix_all`, `vault_norms`, `vault_foreign_check`, `vault_code_tag`, `vault_token_service`, `vault_doc_staleness`.
Razones para no exponerlas: operan sobre el repo del estándar, no sobre el vault del consumidor; lanzan subprocesos (`vault_gate` ≈ 600 s por puerta,
`toolkit_audit` 2400 s, contra un mínimo de timeout MCP de 120 s) y git (AP-68); y sin TLS/permisos finos serían superficie de DoS.

Matices:
1. **`vault_doc_staleness` (solo `--check`)**: sí exponer. Es lectura, barata y es la que hoy está en rojo en este vault (C-08). Hace falta que el consumidor la pueda correr.
2. **`vault_norms`**: exponer únicamente `--audit`/lista. `--rebuild` escribe. Requiere filtro de argumentos por perfil (no una tool nueva).
3. **`vault_fix_all`**: solo perfil `admin`, y **no ejecutarla en este vault** hasta decidir C-08. **`vault_foreign_check`** y **`vault_token_service`**: nunca por MCP
   (la primera recibe una `--root` arbitraria; la segunda gestiona credenciales).

### 4.2 Las 97 expuestas: partirlas en perfiles

El catálogo ya declara `side_effects` por tool: **21 de lectura, 76 con escritura**. Hoy el servidor remoto da las 76 a cualquier token válido.

| Perfil | Tools | Notas |
|---|---|---|
| `lectura` (21) | `vault_read`, `vault_list`, `vault_search`, `vault_context_pack`, `vault_subgraph`, `vault_query_parse`, `vault_impact`, `vault_timeline`, `vault_diff`, `vault_audit`, `vault_validate`, `vault_sanacion`, `vault_gobernanza`, `vault_graph_inspect`, `vault_knowledge_get`, `vault_pattern_list`, `vault_backup_list`, `vault_code_query`, `vault_arquitectura_en`, `vault_tokens`, `vault_token_counter` | Perfil por defecto para tokens de consulta. `side_effects` es declarativo: verificar que `vault_audit`/`vault_sanacion` no escriban trazas fuera del vault (AP-36) |
| `agente` (14 hoy) | `vault_write`, `vault_read`, `vault_search`, `vault_audit`, `vault_context_pack`, `vault_validate`, `vault_project`, `vault_preferences`, `vault_reindex`, `vault_section`, `vault_delta`, `vault_drift_detect`, `vault_delete`, `vault_standard_upgrade` | **Sacar `vault_delete` y `vault_standard_upgrade`** del perfil agente: destructiva y de migración. Un agente no debe borrar sin perfil superior |
| `editor` (≈45) | las `*_save` de dominio (`vault_bug_save`, `vault_requirement_save`, `vault_qa_save`, `vault_runbook_save`, …), `vault_append`, `vault_merge`, `vault_move`, `vault_supersede`, `vault_relation_add`, `vault_ingest`, `vault_tags`, `vault_quarantine` | `vault_move` queda condicionado a D-04 (deja índices de dominio fantasma) |
| `custodia` / `admin` (≈17) | `vault_delete`, `vault_restore`, `vault_restore_base64`, `vault_backup`, `vault_backup_base64`, `vault_undo`, `vault_history_compact`, `vault_migrate_docs`, `vault_migrate_rollback`, `vault_graph_fix`, `vault_fix_brackets`, `vault_frontmatter_heal`, `vault_init`, `vault_onboard`, `vault_sdd_init`, `vault_standard_upgrade`, `vault_propagate` | `vault_restore_base64`/`vault_backup_base64` son los únicos nativos en JS con contención léxica: **no abrir hasta la fase 4**. `vault_propagate` toca otros repos: regla 8, solo bajo petición explícita |

Condiciones previas a cualquier exposición más amplia: TLS ya resuelto (certificado fijado); falta **autorización por tool/perfil por token**,
separar `ok` de `exit_code` en gates, y rotar el token (circuló por el chat y por el historial de comandos).

## 4b. Fase 0 — revalidación sobre `09b2f6d` (2026-10-29, solo lectura)

Revisión de código, no ejecución de reproductores completos. «Confirmado» = el código
descrito sigue en `main`; no prueba por sí solo que el síntoma ocurra.

| Resultado | Ítems |
|---|---|
| Confirmado en `main` | A-01, A-02, A-04 (reproducido: `slugify_strict(...)[:60]` termina en `-`), A-06, A-08, A-10, A-11, A-12, A-14, A-15 (límite declarado), A-16, A-18, A-21, A-22, B-03, B-05 (`qa_verdict_ref`/`owner_decision_ref` siguen `PENDIENTE`, esperado) |
| Parcial / no concluyente | A-05 (el comentario ya no cita AP-13; falta probar timestamps inválidos), A-07 (`merkle_de` descarta ficheros ilegibles; `verificar` sí devuelve `intact`/`status`, pero compara raíces calculadas sobre ese conjunto recortado), A-09 (solo `KeyboardInterrupt` en `vault_errors.py:121` y `cli/vault_cli.py:557`; no probado), A-20 (no hallé el contador en `vault_requirement_save.py`) |
| Confirmados (segunda pasada) | B-01: `release.yml` lee `release_authorized`, CI `success` y ancestría, y no contiene `qg_statuses` ni `qa_verdict_ref`; B-02: `product_tree_sha` está en `CANDIDATO-RELEASE.yaml` y el workflow no lo lee (ata por ancestría); B-04: el colector está en `audits/fase2/colector_qg.py` y ni `.github/` ni `vault_gate.py` lo referencian; A-17: el manifiesto no tiene encabezado `### Grupo` para 32, 33, 35 y 36; D-01: AP-13 (`vault_norms.py:206`) solo comprueba presencia de `createdAt`/`updatedAt`/`id`, no formato; D-05: `vault_requirement_save.py` no tiene `--list` |
| Parcial | D-04: `vault_move.py` sí refresca el índice de sección y el grafo; no verifiqué los 6 índices de dominio ni `.bugs-index.json` (requiere fixture) |
| Distinto de lo descrito | A-19: sin coincidencias de `herramienta` en `vault_doc_counts.py` (el enunciado no se ubica) |
| Sin revalidar | A-03, A-13 (límite declarado), B-06 (decisión del propietario), C-01..C-12 (contenido del vault, no del repo), D-02, D-03, D-06, D-07 |

Consecuencia para el plan: los dos críticos B-01 y B-02 **se confirman** (la puerta de
publicación no lee `qg_statuses`, `qa_verdict_ref` ni `product_tree_sha`), y la Fase 1 puede
partir de A-02, B-01 y B-02 con un test que falle primero. Ningún ítem de «distinto» ni «parcial»
se debe corregir sin reproductor que falle primero.

## 5. Qué no sé

- Fase 0 completa solo para ~24 de los 39 ítems (ver 4b); no abrí el código del servidor remoto (puede diferir del checkout).
- No sé si `side_effects: []` equivale a «no escribe nada» en las 21 tools de lectura.
- Las 30 tools no expuestas las agrupé por lectura del catálogo local de v41.25; el servidor remoto podría tener otro catálogo.
- Del contenido de ~90 notas (índices y stubs generados) solo vi títulos y estado.


## 6. Estado de aplicación (2026-10-30, local, sin push)

Resultado de aplicar la tabla consolidada de remediaciones a este repo. Nada se borró; lo que no se puede cerrar aquí queda declarado con su test.

| Ítem | Estado | Commit / dónde |
|---|---|---|
| A-04, A-05, A-08, A-09, A-12, A-16 | hechos | `87bf418`, `bb7489f`, `290b55e`, `e2f6533`, `f419422`, `de2ab57` |
| A-03 | hecho: presupuesto propio (`PRESUPUESTO_S`) y fracción máxima declarada, con test | `65fc19e` |
| A-15 | hecho: el lock pliega la caja solo si el disco no la distingue | `9ccf7f2` |
| A-11, A-13 | límite declarado en `vault_blueprint.DEUDA_DECLARADA` con test | `ec97352`, `d09c462` |
| B-04 | límite declarado con test | `d1ac5da` |
| C-03 | hecho: el inventario de `15_Tests` clasifica por palabra entera y solo ficheros de test | `f8af588` |
| D-01 a D-06 | hechos | `e176303`, `8bc42bf`, `1bc5e37`, `70a3fc2`, `7b2e6e7`, `7ed183c` |
| D-07 | límite declarado: `round_id` no existe en el contrato ni en ninguna tool; declararlo sin quien lo escriba sería inventarlo | `02d072b` |
| A-20 | hecho: el bloque de Normas pasa bajo `### Grupo 35`, 29–31 se renumeran a 28–30 y Bootstrap estrena `### Grupo 31`; `tests/test_manifiesto_numeracion_de_grupos.py` exige que cada número sea el `group_id` de las tools que el bloque cita | `d2392f9` |
| A-19 | hecho: `vault_doc_counts` vigila «sus N herramientas», «\| N herramientas con», «N tools rápidas en JavaScript» y «N tools via subprocess»; `--fix` llevó 76/76/~10/~66 a 127/127/2/125 y la columna de ejemplos JS-native, que AP-48 desmiente, queda anotada `superseded_by` | `4c644a0` |
| A-18 | hecho: el test, que exige cada tool activa en el bloque `### Grupo N` de su `group_id` (no en cualquier parte de la sección), encontró 18 y no 13 (cinco tenían su entrada escrita en el bloque de otro grupo); las 18 quedan nombradas en el bloque de su grupo con la descripción del catálogo MCP, sin contrato nuevo | este commit |
| A-22 | re-medido el 2026-10-30 sobre el HEAD: sigue abierto (10 de 25 variables fuera del manifiesto) | pendiente |
| `requirement_state` (D-02) | no existe en este repo; no se inventó | — |
| C-09 | no es defecto: `es_nota_indexable` rechaza la nota suelta en la raíz por diseño (AP-15); la salida es mover la nota a `00_System/` en el vault | — |
| C-12 | ya resuelto en el código (`vault_audit` no cuenta `99_Index/tag-index.md` como nota); el 1 huérfano venía de una copia instalada anterior | — |
| C-01, C-02, C-04 a C-08, C-10, C-11 | contenido del vault ajeno, solo lectura aquí | — |
| C-08 | decisión del dueño: regenerar los 5 derivados destruye la reproducción | abierta |
| B-01, B-02, B-05 | hechos: la puerta de `release.yml` lee los 8 QG, ata el árbol (`product_tree_sha`) y exige referencias que sean ficheros de `audits/` o centinela declarado; con test que ejerce la puerta | `f01c3f5`, `1ec050b` |
| B-03 | hecho: `vault-ci.yml` se dispara también con tags `v*` | `de0d13c` |
| B-06 | decisión del propietario (A/B/C de la política de certificación) | abierta |
