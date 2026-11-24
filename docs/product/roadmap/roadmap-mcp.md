# Roadmap — MCP Server

<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

**Versión actual:** `v41.27` (misma versión que el estándar; `tools-catalog.json` derivado)
**Política de backend (`AP-48`):** solo las 2 tools sin equivalente Python (`vault_backup_base64`, `vault_restore_base64`) son JS-native. Escalar backends paralelos en Node está prohibido por `AP-48` (`vault_mcp_catalog --check-contracts`) para evitar divergencia de contratos.

---

## Problemas y prioridades vigentes (P0-P2)

| ID | Problema | Prioridad | Estado |
|---|---|---|---|
| P0 | `tools-catalog.json` desincronizado con Python | P0 | Entregado (`vault_mcp_catalog --check`) |
| P0 | Sin coordinación de concurrencia RW en el servidor MCP | P0 | Entregado (`AsyncRWCoordinator` + `access_mode` CQRS) |
| P1 | Latencia de arranque Python por llamada MCP | P1 | En curso (optimización de imports y proyecciones de lectura) |
| P1 | Secret scan con falsos positivos en código de ejemplo | P1 | Abierto |
| P2 | Multi-vault discovery y cobertura de resources `vault://` | P2 | Parcial (`VAULT_SCAN_ROOTS`, `vault://graph`, `vault://health`) |

---

## Hitos

### Entregado (`v40.x` – `v41.27`)

- [x] `vault_mcp_catalog --sync` genera `tools-catalog.json` desde Python
- [x] `vault_mcp_catalog --check` y `--check-contracts` (`AP-48`) fallan si hay divergencia o backends duplicados
- [x] `tools/call` y `tools/list` operativos (stdio + HTTP/SSE con token Bearer `SP-04`, `--host` y `--tls-cert/--tls-key`)
- [x] Guard chain pre-escritura (secret scan, bracket balance, Mermaid syntax, content gate, tags)
- [x] Pre-commit hook sincroniza derivados automáticamente
- [x] Coordinador CQRS asíncrono (`AsyncRWCoordinator`: lecturas paralelas acotadas por `VAULT_MCP_MAX_READS`, escrituras por carpeta y barrera global)

### Próximos hitos

- [ ] Reducción de latencia en lecturas frecuentes (imports diferidos y proyecciones indexadas sin escaneo O(N))
- [ ] Secret scan con allowlist configurable
- [ ] Ampliación de resources `vault://status` y `vault://norms`
- [ ] Evaluación de worker persistente solo-lectura (sujeto a banco de métricas y decisión de aislamiento A-06)

---

## Métricas de éxito

| Métrica | Target |
|---|---|
| Cumplimiento `AP-48` (sin implementación paralela JS/Python) | 100 % (`check-contracts` en verde) |
| Cobertura de `tools-catalog.json` | 100 % |
| Paralelismo seguro en lecturas MCP (`VAULT_MCP_MAX_READS`) | Hasta 4 concurrentes sin deadlock ni carreras |
| Tiempo guard chain por operación | < 20 ms |
| Pre-commit sync check | Verde |
