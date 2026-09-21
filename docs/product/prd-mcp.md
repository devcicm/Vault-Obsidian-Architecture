# PRD — MCP (Model Context Protocol Server)

**Producto:** Vault-Obsidian-Architecture MCP Server
**Versión target:** v1.0
**Fecha:** 2026-09-20

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

> "Expone 116 tools como herramientas MCP con guard chain de validación
> (secret scan, bracket balance, Mermaid syntax, content gate)."

---

## 4. Scope IN

- Protocolo: JSON-RPC 2.0 sobre stdio + SSE/HTTP
- Commands: `tools/call`, `tools/list`
- Resources: `vault://graph`, `vault://health`, `vault://status`
- JS-native tools: 9 tools implementadas en Node.js puro (sin npm deps)
- Guard chain: secret scan, bracket balance, Mermaid syntax, content gate,
  referenced notes validation
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

- [ ] `tools/call` ejecuta cualquier tool del catálogo
- [ ] `tools/list` devuelve el catálogo completo
- [ ] Resources `vault://` resuelven correctamente
- [ ] Guard chain bloquea secrets, brackets, Mermaid inválido
- [ ] JS-native tools funcionan sin Python
- [ ] `tools-catalog.json` sincronizado con Python
- [ ] Tests de smoke contra MCP server
- [ ] Gates: `vault_gate --strict` verde
