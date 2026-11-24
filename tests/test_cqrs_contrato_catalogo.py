"""TDD Fase B: contrato único de concurrencia CQRS (`access_mode`) y `VAULT_MCP_MAX_READS`.

Verifica que:
1. `vault_mcp_catalog` declara `ACCESS_MODES = ("read", "write", "global")` y
   `GLOBAL_SCOPE_TOOLS` como fuente única (AP-05/AP-57).
2. `cli/scheduler.GLOBAL_SCOPE_TOOLS` consume el mismo conjunto canónico sin
   divergencia.
3. `mcp/nodejs/tools-catalog.json` publica `access_mode` por cada tool y
   `global_scope_tools` en la raíz, y `check_sync()` falla si divergen.
4. `VAULT_MCP_MAX_READS` está declarada en `vault.kernel.entorno` y sincronizada
   en `mcp/nodejs/env-table.json` (default 4, entero).
"""

from __future__ import annotations

import json

from apoyo import ROOT


def test_catalogo_declara_access_mode_y_global_scope_canonicos():
    import vault_mcp_catalog as cat
    from cli import scheduler

    assert cat.ACCESS_MODES == ("read", "write", "global")
    assert set(cat.GLOBAL_SCOPE_TOOLS) == set(scheduler.GLOBAL_SCOPE_TOOLS)
    assert cat.access_mode("vault_backup", cat.TOOLS_CATALOG["vault_backup"]) == "global"
    assert cat.access_mode("vault_write", cat.TOOLS_CATALOG["vault_write"]) == "write"
    assert cat.access_mode("vault_search", cat.TOOLS_CATALOG["vault_search"]) == "read"

    for name, entry in cat.TOOLS_CATALOG.items():
        modo = cat.access_mode(name, entry)
        assert modo in cat.ACCESS_MODES, (name, modo)
        if name in cat.GLOBAL_SCOPE_TOOLS:
            assert modo == "global", name


def test_tools_catalog_json_publica_access_mode_y_global_scope_tools():
    import vault_mcp_catalog as cat

    datos = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    assert datos.get("global_scope_tools") == sorted(cat.GLOBAL_SCOPE_TOOLS)
    for name, entry in cat.TOOLS_CATALOG.items():
        assert datos["tools"][name].get("access_mode") == cat.access_mode(name, entry), name


def test_check_sync_detecta_desfase_de_access_mode(tmp_path):
    import vault_mcp_catalog as cat

    copia = tmp_path / "tools-catalog.json"
    datos = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    datos["tools"]["vault_write"]["access_mode"] = "read"
    copia.write_text(json.dumps(datos), encoding="utf-8")

    r = cat.check_sync(str(copia))
    assert r["ok"] is False
    assert any("access_mode" in d for d in r["diffs"]), r["diffs"]


def test_vault_mcp_max_reads_declarada_en_entorno_y_env_table():
    from vault.kernel import entorno

    assert "VAULT_MCP_MAX_READS" in entorno.VARIABLES
    var = entorno.VARIABLES["VAULT_MCP_MAX_READS"]
    assert var.tipo == "entero" and var.default == 4

    tabla = json.loads((ROOT / "mcp" / "nodejs" / "env-table.json").read_text(encoding="utf-8"))
    por_nombre = {v["name"]: v for v in tabla["variables"]}
    assert "VAULT_MCP_MAX_READS" in por_nombre
    assert por_nombre["VAULT_MCP_MAX_READS"]["default"] == 4
