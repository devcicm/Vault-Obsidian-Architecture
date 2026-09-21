# Roadmap — MCP Server

**Horizonte:** 6 meses (Q4 2026 — Q2 2027)
**Versión inicial:** v1.0

---

## Problemas a resolver (P0-P2)

| ID | Problema | Prioridad | Hito |
|----|---------|-----------|------|
| P0 | `tools-catalog.json` desincronizado con Python | P0 | v1.0 |
| P1 | JS-native tools coverage limitada (9 de 116) | P1 | v1.1 |
| P1 | Secret scan con falsos positivos en código de ejemplo | P1 | v1.1 |
| P2 | Multi-vault discovery sin configuración | P2 | v1.2 |
| P2 | Resources `vault://` coverage parcial | P2 | v1.2 |

---

## Milestones

### v1.0 (Q4 2026)

- [ ] `vault_mcp_catalog --sync` genera `tools-catalog.json` desde Python
- [ ] `vault_mcp_catalog --check` falla si divergen
- [ ] `tools/call` y `tools/list` operativos
- [ ] 9 JS-native tools funcionando
- [ ] Guard chain: secret scan, bracket balance, Mermaid syntax, content gate
- [ ] `tools-catalog.json` sincronizado con Python (pre-commit hook)

### v1.1 (Q1 2027)

- [ ] +20 JS-native tools (para tools de consulta frecuentes)
- [ ] Secret scan con allowlist configurable
- [ ] `VAULT_SCAN_ROOTS` para multi-vault discovery
- [ ] Resources `vault://graph` y `vault://health` completos
- [ ] Trace log persistente en sesión

### v1.2 (Q2 2027)

- [ ] Resources `vault://status` y `vault://norms`
- [ ] +50 JS-native tools (cobertura 50%+)
- [ ] Integración con MCP HTTP mode (para Testing)
- [ ] Tests de smoke automatizados contra server
- [ ] MCP spec compliance verificado

---

## Métricas de éxito

| Métrica | Target |
|---------|--------|
| JS-native tools | 50+ (de 116) |
| tools-catalog.json coverage | 100% |
| Tiempo guard chain por operación | < 20ms |
| Secret scan falsos positivos | < 1% |
| Pre-commit sync check | Verde |
