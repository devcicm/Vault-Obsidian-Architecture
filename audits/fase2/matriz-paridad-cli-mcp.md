# Matriz de paridad CLI ↔ MCP — fase 2 (L3)

Derivado de la ejecucion real sobre el artefacto instalado. Generado por `python audits/fase2/paridad_cli_mcp.py`.

- Tools expuestas por el servidor MCP instalado: **97**
- Verificador de contrato AP-40 (`vault_mcp_catalog --check-params`): exit **0**
- Casos comparados: **5** · veredicto: **CONFORME**
- Alcance declarado: paridad funcional probada en 5 casos de 97 tools expuestas por el servidor MCP; el contrato de TODAS las tools lo cubre el verificador AP-40

| Operación | Expuesta por MCP | Campos comparados | CLI | MCP | Coincide |
|---|---|---|---|---|---|
| `vault_read` | sí | path | `{"ok": false, "path": "07_Knowledge/nota-paridad.md"}` | `{"ok": false, "path": "07_Knowledge/nota-paridad.md"}` | sí |
| `vault_search` | sí | query | `{"ok": true, "total": 1}` | `{"ok": true, "total": 1}` | sí |
| `vault_list` | sí | folder | `{"ok": true}` | `{"ok": true}` | sí |
| `vault_write` | sí | folder, title, content, tags | `{"ok": true, "created": false, "path": "07_Knowledge/nota-de-paridad.md"}` | `{"ok": true, "created": false, "path": "07_Knowledge/nota-de-paridad.md"}` | sí |
| `vault_write` | sí | folder, title, content, tags | `{"ok": true, "updated": 6, "path": "07_Knowledge/nota-de-paridad.md"}` | `{"ok": true, "updated": 6, "path": "07_Knowledge/nota-de-paridad.md"}` | sí |

## Criterio de equivalencia

Se comparan resultados NORMALIZADOS (ok, rutas, contadores y codigos de error), no la igualdad literal de las respuestas: el transporte de cada adaptador es distinto por diseño, y lo que debe coincidir es el contrato de negocio (misma operacion, mismos argumentos, mismo efecto y mismo significado de error).

