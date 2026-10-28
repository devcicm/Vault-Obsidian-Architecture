# PRD — MCP (Model Context Protocol Server)

<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

**Producto:** Vault-Obsidian-Architecture MCP Server
**Versión target:** v1.0
**Fecha:** 2026-09-20

> **RECONCILIACIÓN (2026-10-27, R15).** Este PRD es un documento de objetivos
> con fecha: sus cifras (116/117 tools, 9 JS-native) eran el target de
> septiembre y NO se reescriben. El estado medido vigente lo publica
> `audits/fase2/MATRIZ-CAPACIDAD-PRODUCTO.md`: **97 tools expuestas por MCP**
> (126 en el catálogo; 2 JS-native), guard chain y recursos `vault://`
> operativos, verificados por el E2E de terceros y la CI del candidato (R23, 2026-10-28:
> Windows + Linux, 27 jobs; ver `audits/fase2/CANDIDATO-RELEASE.yaml`). Cualquier promesa de capacidad se rige por esa matriz, no por
> este PRD.

---

## 1. Problem Statement

Los agentes LLM necesitan acceso en tiempo real al vault con validación
semántica profunda. La interacción MCP es la superficie principal para
agentes conversacionales.

**Slogan:** "Cualquier IA compatible usa las tools sin configuración."

---

## 2. Vision

Servidor MCP monolítico CERO-dependencias npm para cualquier IA compatible.
Expone 116 tools como herramientas MCP con guard chain de validación.

---

## 3. Promise (Product)

> "Expone 117 tools como herramientas MCP con guard chain de validación
> (secret scan, bracket balance, Mermaid syntax, content gate)." `vault_gobernanza`
> es la tool de gobernanza del MCP, invocable como `__module__:vault.gobernanza.tool`.

---

## 4. Scope IN

- Protocolo: JSON-RPC 2.0 sobre stdio + SSE/HTTP
- Commands: `tools/call`, `tools/list`
- Resources: `vault://graph`, `vault://health`, `vault://status`
- JS-native tools: 9 tools implementadas en Node.js puro (sin npm deps)
- Guard chain: secret scan, bracket balance, Mermaid syntax, content gate,
  referenced notes validation
- **Tool `vault_gobernanza`**: validación de contenido contra normas MCP via
  `__module__:vault.gobernanza.tool` prefix
- Multi-vault discovery (`VAULT_SCAN_ROOTS`)
- Trace log de ejecuciones
- Versionado con `tools-catalog.json`

---

## 5. Scope OUT

- Scheduling de olas (ejecución secuencial)
- `--verify-integrity`
- Batch execution

---

## 6. Constraints

- CERO npm dependencies (solo `node:*` built-ins)
- Mismo catálogo de tools que CLI
- Misma gobernanza vía `GobernanzaBase`
- El servidor NO posee semántica de dominio — solo adapta las operations

---

## 7. Governance (POO)

Hereda de `GobernanzaBase`; override en `mcp_gobernanza.py`.

**Pre-flight específico:**
- `secret_scan`: AWS keys, GitHub tokens, passwords, API keys, private keys
- `bracket_balance`: wikilinks `[[...]]`, código `[...]`, parens `(...)`, braces `{...}`
- `Mermaid syntax`: graph type, balanced braces
- `content_gate`: mínimo 3 líneas reales, 10 palabras
- `referenced_notes`: validación de notas referenciadas

**Post-flight específico:**
- Trace log de cada ejecución

---

## 8. Risks

| ID | Riesgo | Mitigación |
|----|---------|-----------|
| R1 | `tools-catalog.json` desincronizado con Python | `vault_mcp_catalog --check --strict` en pre-commit |
| R2 | Changes en protocolo MCP rompen agentes | Versionado; changelog |
| R3 | Secret scan con falsos positivos en código example | Allowlist configurable |

---

## 9. Roadmap

Ver [roadmap-mcp.md](./roadmap/roadmap-mcp.md)

---

## 10. Definition of Done

- [x] `tools/call` ejecuta cualquier tool del catálogo
- [x] `tools/list` devuelve el catálogo completo
- [ ] Resources `vault://` resuelven correctamente
- [x] Guard chain bloquea secrets, brackets, Mermaid inválido
- [x] JS-native tools funcionan sin Python
- [x] `tools-catalog.json` sincronizado con Python
- [ ] Tests de smoke contra MCP server
- [x] Gates: `vault_gate --strict` verde
