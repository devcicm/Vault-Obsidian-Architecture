# Matriz de paridad CLI ↔ MCP — fase 2 (L3)

Derivado de la ejecucion real sobre el artefacto instalado. Generado por `python audits/fase2/paridad_cli_mcp.py`.

- Tools expuestas por el servidor MCP instalado: **97**
- Verificador de contrato AP-40 (`vault_mcp_catalog --check-params`): exit **0**
- Casos medidos: **5** (identidad propia por escenario) · veredicto: **CONFORME**
- Alcance: paridad funcional probada en 5 casos con identidad propia (operacion + escenario) de 97 tools expuestas por el servidor MCP; el contrato de TODAS las tools lo cubre el verificador AP-40

| case_id | Operación | Escenario | CLI | MCP | Efectos (CLI) | Efectos (MCP) | Coincide |
|---|---|---|---|---|---|---|---|
| `READ_MISSING` | `vault_read` | leer una nota que no existe | `{"ok": false, "path": "07_Knowledge/nota-paridad.md"}` | `{"ok": false, "path": "07_Knowledge/nota-paridad.md"}` | [] | [] | sí |
| `SEARCH_HITS` | `vault_search` | buscar un termino presente | `{"ok": true, "total": 1}` | `{"ok": true, "total": 1}` | [] | [] | sí |
| `LIST_FOLDER` | `vault_list` | listar una carpeta | `{"ok": true}` | `{"ok": true}` | [] | [] | sí |
| `WRITE_CREATE` | `vault_write` | crear una nota nueva | `{"ok": true, "created": false, "path": "07_Knowledge/nota-de-paridad.md"}` | `{"ok": true, "created": false, "path": "07_Knowledge/nota-de-paridad.md"}` | ['.history/07_Knowledge__nota-de-paridad-<TS>.md', '00_System/.change-log.json', '00_System/change-log.md', '07_Knowledge/nota-de-paridad.md', '99_Index/search-index.json'] | ['.history/07_Knowledge__nota-de-paridad-<TS>.md', '00_System/.change-log.json', '00_System/change-log.md', '07_Knowledge/nota-de-paridad.md', '99_Index/search-index.json'] | sí |
| `WRITE_UPDATE` | `vault_write` | actualizar la nota ya creada | `{"ok": true, "updated": 6, "path": "07_Knowledge/nota-de-paridad.md"}` | `{"ok": true, "updated": 6, "path": "07_Knowledge/nota-de-paridad.md"}` | ['.history/07_Knowledge__nota-de-paridad-<TS>.md', '00_System/.change-log.json', '00_System/change-log.md', '07_Knowledge/nota-de-paridad.md', '99_Index/search-index.json'] | ['.history/07_Knowledge__nota-de-paridad-<TS>.md', '00_System/.change-log.json', '00_System/change-log.md', '07_Knowledge/nota-de-paridad.md', '99_Index/search-index.json'] | sí |

## Criterio de equivalencia

Se comparan resultados NORMALIZADOS (ok, rutas, contadores y codigos de error) Y los EFECTOS REALES sobre el runtime: ficheros creados, modificados y eliminados, con su contenido normalizado (los campos volatiles —id, createdAt, updatedAt— se enmascaran porque cambian entre dos ejecuciones identicas). Ademas se comprueba que no se modifica nada FUERA del runtime autorizado.

