# `scripts/_archived/` — tools reemplazadas, no derogadas

Este directorio existe por la **política de no-derogación** del estándar: nada se
elimina. Una tool que dejó de ser el camino recomendado se archiva conservando su
contrato, y se anota quién la reemplaza. Si algo aquí parece obsoleto, lo es: esa
es exactamente la razón de que siga existiendo y de que quede escrito por qué.

Qué implica estar en esta carpeta:

- **No** están en `vault_mcp_catalog.TOOLS_CATALOG` ni se exponen por MCP.
- **No** entran en los conteos de tools activas de la documentación.
- **Sí** deben compilar (`python -m py_compile scripts/_archived/*.py`, job de lint
  del CI) y **sí** conservan su interfaz de línea de comandos original.

## Mapa de sucesión

| Archivada | `superseded_by` | Por qué |
|---|---|---|
| `vault.py` | `cli/vault_cli.py` | Despachador por subprocess reemplazado por la CLI consolidada, que importa las tools en proceso. |
| `vault_create.py` | `vault_write.py` | La creación de notas se unificó con la escritura: un único camino con guards, `.history` y ledger AP-37. |
| `vault_help.py` | `vault_mcp_catalog.py` | La ayuda se deriva del catálogo canónico en vez de mantener su propia vista. |
| `vault_migrate.py` | `vault_migrate_docs.py` | Migración con clasificación, reporte de rollback (AP-10) y trazabilidad. |
| `vault_render.py` | `vault_diagram_export.py` | Renderizado de Mermaid con validación AP-25 y export contenido en el vault (AP-36). |
| `vault_reorganize.py` | `vault_move.py` | El movimiento puntual de notas actualiza wiki-links, `search-index.json` y `graph.json`. |
| `vault_session.py` | `vault_delta.py` | La observabilidad de sesión se deriva del cambio real registrado, no de un log escrito a mano. |
| `vault_tools.py` | `cli/vault_cli.py` | Script paraguas reemplazado por la CLI consolidada. |

## Estado conocido

`vault_create.py` estaba **truncado** y no compilaba (`IndentationError` en el
`print` final del `main`). Se reparó el bloque —dedent y código de salida derivado
del resultado— sin cambiar su comportamiento ni sacarla de este directorio.
