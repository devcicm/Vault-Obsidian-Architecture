## Resumen

> Archivado el 2026-10-01 desde la raíz del repo (`PR_BODY.md`, entonces
> excluido de git): cuerpo del PR del checkpoint 3. Se conserva como registro;
> las cifras que cita son las de aquel momento.

CHECKPOINT 3 completo — `vault_gobernanza` integrada como tool de primera clase del estándar.

### Qué se entrega

| Componente | Cambio |
|---|---|
| **Tool `vault_gobernanza`** | Existente: `vault/gobernanza/tool.py` — `python -m vault.gobernanza.tool --content "..."` |
| **Catálogo** | 116→117 tools, `vault_gobernanza` en grupo 6 (Salud del Vault), naturaleza `custodia` |
| **MCP server** | Invoca como `python -m vault.gobernanza.tool` via `__module__:` prefix |
| **Contratos** | tool-spec.json con entrada completa para `vault_gobernanza` |
| **Distribución** | `vault_gobernanza` NO es distributable via `vault_toolkit/operations/` — es una puerta de gobernanza del MCP |

### Fixes de esta tanda

- **`cli/resolver.py`**: `getattr(spec, 'origin', None)` — evita `AttributeError` en mocks; `spec is None` → `None` para fallback legacy
- **`vault/gobernanza/__init__.py` + `tool.py`**: `sys.path.insert(0, scripts/)` — permite import de `vault_regex` en consumo externo
- **`mcp_gobernanza.py`**: usa `RE_WIKILINK` canónico (O(n), no O(n²))
- **`cli/registry.py`**: elimina `sys.path.insert` redundante
- **Tests**: mocks corregidos + expectativas hardcodeadas actualizadas a `vault_toolkit.operations.*`

### Verificación

- **22/22 gates** green
- **40 tests** passing (incluyendo los 3 resolver y el de promises instaladas)
- CLI verificada: `python -m vault.gobernanza.tool --content "..."` funciona

### Docs

Conteos auto-derivados: 116→117 tools, 99→100 write tools, 3198→3199 tests. Todo derivado de los registros canónicos.

---

**Cierre**: `product/product-readiness` → `main`
