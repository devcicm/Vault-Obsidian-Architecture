# Vault MCP Monolith — Plan de Implementacion

> **Estado:** En construccion — Fase 1/8  
> **Version:** v37.0 (SDD)  
> **Fecha inicio:** 2026-07-01  
> **Arquitecto:** CI + Kimi (deepseek-v4-pro)

---

## 0. Filosofia: Spec-Driven Documentation + Manifiesto MCP

El MCP no es solo un servidor de herramientas — es un **observador y custodio del grafo de conocimiento**. El manifiesto SDD dice: *"La documentacion es primordial"*.

Principios del monolito MCP:

| Principio | Significado |
|-----------|-------------|
| **Observar** | Detectar cambios automaticamente (file watcher + delta) |
| **Validar** | Cada write pasa por una cadena de guardas (guard chain) |
| **Trazar** | Toda mutacion tiene registro inmutable (trace log) |
| **Versionar** | Snapshots pre/post de cada operacion (Merkle root) |
| **Sanar** | Auto-fix de anomalias detectadas (brackets, links rotos) |
| **Servir** | Las IAs se conectan directamente, sin registro en harness |

---

## 1. Arquitectura

```
                     ┌─────────────────────────────┐
   AI (Claude/etc) ──▶  MCP Protocol (SSE / stdio)   ──┐
                     └─────────────────────────────┘   │
                                                       ▼
         ┌─ vault-mcp-server.mjs (~3200 lineas) ───────────────────┐
         │                                                           │
         │  CAPA 1: Transport (dual)                                 │
         │  ├── stdioMode()       → stdin/stdout JSON-RPC            │
         │  └── sseMode(port)     → HTTP/SSE en localhost:3000       │
         │                                                           │
         │  CAPA 2: MCP Protocol (JSON-RPC 2.0 nativo)               │
         │  ├── initialize, tools/list, tools/call                   │
         │  └── resources/list, resources/read                       │
         │                                                           │
         │  CAPA 3: Tool Registry (71 tools)                         │
         │  ├── JS-native (fast path, ~10 tools)                     │
         │  │   vault_read, vault_list, vault_search,                │
         │  │   vault_graph, vault_graph_inspect, vault_tokens       │
         │  └── Python subprocess (~61 tools)                        │
         │      child_process.spawn("python", ["scripts/v_*.py"])    │
         │                                                           │
         │  CAPA 4: Validacion (guard chain)                         │
         │  ├── secret scan, content gate                            │
         │  ├── bracket balance, empty links, path-anchored          │
         │  ├── table brackets (NUEVO)                               │
         │  ├── referenced notes existence + content (NUEVO)         │
         │  ├── Mermaid syntax                                       │
         │  └── CIA fields                                           │
         │                                                           │
         │  CAPA 5: Cambio Detection (file watcher)                  │
         │  ├── fs.watch recursivo con debounce 500ms                │
         │  ├── SHA-256 hash comparison (vault_delta)                │
         │  ├── Git integration (vault_drift_detect)                 │
         │  └── Snapshot protocol (pre/post)                         │
         │                                                           │
         │  CAPA 6: Traceability Engine                              │
         │  ├── TraceLog (immutable, dual JSON+MD)                   │
         │  ├── Mutation audit (quien, que, cuando, diff)            │
         │  └── Merkle verification                                  │
         │                                                           │
         │  CAPA 7: Observability                                    │
         │  ├── HealthCheck (broken links, orphans, stale,           │
         │  │   duplicates, bracket anomalies, Mermaid errors)       │
         │  ├── QualityScore (9 dimensiones DQ)                      │
         │  └── NextActions (prescriptive)                           │
         │                                                           │
         │  CAPA 8: Idempotencia + Estados + Versiones               │
         │  ├── LockManager (file_lock port a JS)                    │
         │  ├── AtomicWriter (atomic_write port a JS)                │
         │  ├── StateStore (CAS para idempotencia)                   │
         │  ├── VersionManager (standard-version.json)               │
         │  └── VaultVersioning (Merkle snapshots)                   │
         │                                                           │
         │  CAPA 9: Impact/Propagation                                │
         │  ├── BFS reverse-graph traversal                          │
         │  ├── Strategy system (conservative/transitive/critical)   │
         │  └── Action system (notify/queue/reindex)                 │
         │                                                           │
         │  CAPA 10: Resources (MCP resources URI)                    │
         │  ├── vault://graph.json                                   │
         │  ├── vault://health                                       │
         │  ├── vault://traceability/mutations                       │
         │  ├── vault://catalog                                      │
         │  └── vault://state                                        │
         │                                                           │
         │  CAPA 11: Obsidian Desktop API (validacion externa)       │
         │  ├── validateNotePath() via http://localhost:27124        │
         │  ├── validateWikilinks() contra indice Obsidian           │
         │  └── Fallback filesystem si Obsidian no esta corriendo    │
         │                                                           │
         └───────────────────────────────────────────────────────────┘
```

---

## 2. Estructura de archivos

```
mcp/
├── PLAN.md                              ← Este documento
├── nodejs/
│   └── vault-mcp-server.mjs             ← MONOLITO Node.js
└── python/
    └── vault_mcp_server.py              ← Equivalente Python (futuro)
```

---

## 3. Fases de implementacion

### F1: MCP Core Protocol + stdio transport
| Item | Descripcion | Lineas |
|------|-------------|--------|
| JSON-RPC 2.0 handler | `initialize`, `initialized`, `tools/list`, `tools/call` | ~200 |
| stdio transport | Lee stdin linea por linea, escribe JSON a stdout | ~100 |
| Zero dependencies | Solo `node:fs`, `node:path`, `node:child_process` | — |
| **Total F1** | | **~300** |

**Verificacion:**
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | node mcp/nodejs/vault-mcp-server.mjs
```

---

### F2: Tool Registry + Python subprocess
| Item | Descripcion | Lineas |
|------|-------------|--------|
| Port TOOLS_CATALOG | 71 tools de `vault_mcp_catalog.py` a JS object | ~200 |
| `tools/list` | Retorna inputSchema completo para cada tool | ~50 |
| Python dispatch | `spawn("python", ["scripts/v_*.py", ...])` con timeout 120s | ~100 |
| **Total F2** | | **~350** |

---

### F3: JS-native backend
| Item | Descripcion | Lineas |
|------|-------------|--------|
| normalizeStem | Port de `vault_io.normalize_stem` | ~10 |
| extractWikilinks | Port de `vault_regex.extract_wiki_links_strict` | ~30 |
| parseFrontmatter | Port de `vault_lib.parse_frontmatter` | ~40 |
| Bracket regex | `RE_NESTED_*`, `RE_EMPTY_LINK`, `RE_PATH_ANCHORED` | ~30 |
| vault_read | `fs.readFile` + frontmatter parse | ~30 |
| vault_list | `fs.readdir` recursivo | ~30 |
| vault_search | `fs.readFile` + regex grep | ~40 |
| vault_graph | Construye `{nodes, edges}` desde wikilinks | ~80 |
| vault_graph_inspect | Calcula broken links, orphans, hubs, duplicates | ~150 |
| vault_tokens | Conteo heuristico de tokens | ~30 |
| vault_fundamentals | Validacion AP-17 a AP-24 | ~60 |
| **Total F3** | | **~530** |

---

### F4: SSE/HTTP transport
| Item | Descripcion | Lineas |
|------|-------------|--------|
| HTTP server | `node:http` nativo en `127.0.0.1:3000` | ~80 |
| SSE endpoint | `GET /sse` con keep-alive y event stream | ~60 |
| Message endpoint | `POST /message` recibe JSON-RPC, responde JSON | ~50 |
| Health endpoint | `GET /health` | ~30 |
| **Total F4** | | **~220** |

---

### F5: Guard Chain + Validadores (NUEVOS)
| Item | Descripcion | Lineas |
|------|-------------|--------|
| **validateTableBrackets** | Escanea tablas markdown, detecta `[[` o `]]` incompletos por celda | ~80 |
| **validateReferencedNotes** | Todo wikilink debe apuntar a nota existente con contenido real | ~60 |
| **validateNoteHasContent** | Nota referenciada debe tener >3 lineas reales y >10 palabras | ~40 |
| guardSecretScan | Port de `vault_secret_scan.vault_write_hook` | ~50 |
| guardContentGate | Port de `vault_write._check_content_gate` | ~60 |
| guardBracketBalance | Port de `vault_regex.validate_and_fix` | ~30 |
| guardEmptyLinks | `RE_EMPTY_LINK` check | ~10 |
| guardPathAnchored | Port de `vault_regex.detect_path_anchored` | ~15 |
| guardMermaidSyntax | Port basico | ~30 |
| guardCIAFields | Port de `vault_validate._validate_cia_fields` | ~30 |
| **Total F5** | | **~405** |

---

### F6: Observabilidad + Trazabilidad
| Item | Descripcion | Lineas |
|------|-------------|--------|
| FileWatcher | `fs.watch` recursivo + debounce + hash recomputation | ~100 |
| Snapshot protocol | takeSnapshot + compareSnapshots | ~60 |
| detectBrokenLinks | Port de `vault_audit._detect_broken_links` | ~50 |
| detectOrphans | Port de `vault_audit._detect_orphans` | ~40 |
| detectStale | Port de `vault_audit._detect_stale` | ~30 |
| detectDuplicates | AP-17 (title) + AP-18 (content) | ~50 |
| detectBracketAnomalies | Port de `vault_audit._detect_malformed_wikilinks` | ~60 |
| computeHealthScore | Penalty-based scoring | ~40 |
| generateNextActions | Prescriptive actions | ~50 |
| TraceLog | Dual persistence JSON+MD, immutable audit | ~80 |
| QualityScore | 9 dimensiones DQ | ~100 |
| **Total F6** | | **~660** |

---

### F7: Idempotencia + Estados + Versiones
| Item | Descripcion | Lineas |
|------|-------------|--------|
| LockManager | `file_lock` port a JS (directory-based) | ~60 |
| AtomicWriter | `atomic_write_text` port a JS (temp + rename) | ~50 |
| StateStore | CAS operations sobre `.mcp-state.json` | ~60 |
| VersionManager | `standard-version.json` + migration detection | ~80 |
| VaultVersioning | Merkle snapshots + verify | ~100 |
| BFS Impact | Reverse graph traversal + CIA risk | ~80 |
| Propagation | Strategy/Action system | ~80 |
| **Total F7** | | **~510** |

---

### F8: Resources + Obsidian API + Docs
| Item | Descripcion | Lineas |
|------|-------------|--------|
| MCP Resources | `vault://graph`, `vault://health`, `vault://trace`, etc. | ~80 |
| Obsidian REST client | `localhost:27124` HTTP client | ~80 |
| Fallback validation | Filesystem validation cuando Obsidian no esta | ~50 |
| Startup banner | ASCII art + version + vault info | ~30 |
| **Total F8** | | **~240** |

---

## 4. Resumen de lineas por fase

| Fase | Contenido | Lineas | Acumulado |
|------|-----------|--------|-----------|
| F1 | MCP Core + stdio | 300 | 300 |
| F2 | Tool Registry + Python | 350 | 650 |
| F3 | JS-native backend | 530 | 1180 |
| F4 | SSE/HTTP transport | 220 | 1400 |
| F5 | **Guard Chain + Validadores** | 405 | 1805 |
| F6 | Observabilidad + Trazabilidad | 660 | 2465 |
| F7 | Idempotencia + Estados | 510 | 2975 |
| F8 | Resources + Obsidian API | 240 | **3215** |

---

## 5. Dependencias

| Tipo | Requisito | Notas |
|------|-----------|-------|
| Runtime | Node.js >= 18 | ES modules nativos |
| Runtime | Python >= 3.9 | Para backend Python subprocess |
| Opcional | Obsidian Desktop | Con plugin Local REST API (puerto 27124) |
| npm | **CERO** | Todo con `node:*` built-ins |
| pip | **CERO** adicionales | Usa scripts existentes del repo |

---

## 6. Modos de uso

### Modo stdio (local)
```bash
node mcp/nodejs/vault-mcp-server.mjs
# El cliente MCP lo lanza como proceso hijo
```

### Modo servicio (sin harness)
```bash
node mcp/nodejs/vault-mcp-server.mjs --port 3000
# Las IAs se conectan a http://localhost:3000/sse
```

### Con vault root explicito
```bash
node mcp/nodejs/vault-mcp-server.mjs --vault "C:/Users/.../mi-vault" --port 3000
```

---

## 7. Estrategias reutilizadas del codebase existente

### De vault_io.py
- `_detect_vault_root()` → `detectVaultRoot()`
- `file_lock()` → `LockManager`
- `atomic_write_text()` → `AtomicWriter`
- `normalize_stem()` → `normalizeStem()`

### De vault_regex.py
- `detect_bracket_anomalies()` → `detectBracketAnomalies()`
- `detect_path_anchored()` → `detectPathAnchored()`
- `extract_wiki_links_strict()` → `extractWikilinks()`
- Todos los `RE_*` patterns

### De vault_audit.py
- `_detect_broken_links()` → `detectBrokenLinks()`
- `_detect_orphans()` → `detectOrphans()`
- `_detect_stale()` → `detectStale()`
- `_detect_canonical_shadow()` → `detectDuplicates()`
- `_detect_malformed_wikilinks()` → `detectBracketAnomalies()`
- Penalty-based health scoring

### De vault_delta.py
- `_collect_current_hashes()` → file watcher hash map
- `_compute_delta()` → `computeDelta()`
- `_bfs_impact()` → `bfsImpact()`

### De vault_drift_detect.py
- `_git_changed_since()` → `gitChangedSince()`
- `_hash_changed_since()` → `hashChangedSince()`
- Session snapshot protocol

### De vault_write.py
- `_check_content_gate()` → `guardContentGate()`
- Multi-gate pipeline pattern

### De vault_change_log.py
- Dual persistence (JSON + MD)
- UUID + timestamp + agent = immutable audit record

### De vault_backup.py
- Merkle tree computation → `computeMerkleRoot()`
- Backup verification → `verifySnapshot()`

### De vault_secret_scan.py
- `vault_write_hook()` → `guardSecretScan()`
- Declarative `SECRET_PATTERNS`

### De vault_mcp_catalog.py
- `TOOLS_CATALOG` completo → toolRegistry
- `GROUPS` → toolGroups
- Validator vocabulary

### De vault_quality_check.py
- 9-dimension DQ scoring → `QualityScore`

### De vault_impact.py + vault_propagate.py
- BFS reverse-graph traversal
- Strategy/Action system

---

## 8. Validadores nuevos (no existentes en el codebase)

### 8.1 Table Bracket Validator
**Proposito:** Detectar corchetes incompletos en celdas de tablas markdown.

**Algoritmo:**
1. Detectar filas de tabla: lineas que empiezan y terminan con `|`
2. Por cada fila, split por `|` para obtener celdas
3. Por cada celda, contar `[[` y `]]`
4. Si `opens !== closes` → error con `{row, column, cell_content, type}`

**Output de error:**
```json
{
  "type": "table_bracket_imbalance",
  "row": 15,
  "column": 2,
  "cell_content": "ver [[14_Requirements",
  "detail": "[[ sin ]] de cierre en celda de tabla"
}
```

### 8.2 Referenced Notes Validator
**Proposito:** Bloquear writes que contengan wikilinks a notas inexistentes.

**Diferencia con ghost links actual:** Los ghost links en `vault_write.py` son advisory (no bloquean). Este validador es BLOQUEANTE.

**Algoritmo:**
1. Extraer todos los wikilinks del contenido
2. `normalizeStem(cada link)`
3. Buscar en `_stems_set` (indice de todas las notas)
4. Si no existe → error
5. Si existe pero es stub o vacia → error

### 8.3 Note Has Content Validator
**Proposito:** Verificar que una nota referenciada tiene contenido real (no es stub).

**Algoritmo:**
- >3 lineas reales (excluye frontmatter, vacias, TODOs solitarios)
- >10 palabras reales (excluye markdown markers, puntuacion)
- Si no cumple → error

---

## 9. Log de cambios del plan

| Fecha | Cambio | Autor |
|-------|--------|-------|
| 2026-07-01 | Plan inicial creado. Fases F1-F8 definidas. | CI + Kimi |
| 2026-07-01 | Agregados 3 validadores nuevos (tablas, notas ref, contenido). | CI + Kimi |
| 2026-07-01 | Analisis de 25+ scripts Python para extraer estrategias reutilizables. | Kimi (deepseek-v4-pro) |
|       | Pendiente: implementacion F1. | |

---

## 10. Referencias

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api)
- [Vault Obsidian Architecture — Manifiesto SDD](../vault-obsidian-architecture.md)
- [Scripts README — Tool Catalog](../scripts/README.md)
