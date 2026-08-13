"""La capacidad consulta -> contexto era inalcanzable por MCP (v40.16).

`vault_query_parse` y `vault_context_pack` tomaban la pregunta como
**posicional**. El catálogo publica los parámetros por nombre de flag, así que
`query` no aparecía en el `inputSchema` y el servidor invocaba con `--query`,
que argparse rechazaba. `--check-params` solo medía `publicado ⊆ argparse`, la
dirección que no ve este caso: no sobraba nada, faltaba todo.
"""

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

CATALOGO = RAIZ / "mcp" / "nodejs" / "tools-catalog.json"
CONSULTA = ("vault_query_parse", "vault_context_pack")


def _tools():
    d = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return d.get("tools", d)


def test_la_pregunta_se_publica_en_el_input_schema():
    tools = _tools()
    for nombre in CONSULTA:
        props = (tools[nombre].get("inputSchema") or {}).get("properties", {})
        assert "query" in props, f"{nombre}: MCP no puede pasar la pregunta"


def test_la_forma_nombrada_funciona_de_verdad():
    """No basta con publicarla: la CLI tiene que aceptarla."""
    for nombre in CONSULTA:
        r = subprocess.run(
            [sys.executable, str(RAIZ / "scripts" / f"{nombre}.py"),
             "--query", "que decidimos sobre auth"],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        assert r.returncode == 0, f"{nombre}: {r.stderr[-400:]}"
        assert json.loads(r.stdout)["query"] == "que decidimos sobre auth"


def test_el_posicional_sigue_valiendo():
    """No-derogación: quien lo usaba desde la CLI sigue funcionando."""
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "vault_query_parse.py"), "auth"],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["query"] == "auth"


def test_el_detector_de_posicionales_reconoce_el_caso(tmp_path, monkeypatch):
    """La medida nueva se prueba contra la forma que existía, no solo en verde."""
    import vault_mcp_catalog as cat

    (tmp_path / "falsa.py").write_text("\n".join([
        "import argparse",
        "p = argparse.ArgumentParser()",
        'p.add_argument("query")',
        'p.add_argument("opcional", nargs="?")',
        'p.add_argument("--flag")',
    ]), encoding="utf-8")
    monkeypatch.setattr(cat, "__file__", str(tmp_path / "vault_mcp_catalog.py"))

    assert cat.posicionales_obligatorios("falsa.py") == ["query"], (
        "el posicional obligatorio se ve; el `nargs=\"?\"` y el flag no"
    )


def test_ninguna_tool_del_catalogo_tiene_entrada_inalcanzable():
    import vault_mcp_catalog as cat

    r = cat.check_params()
    assert r["ok"], r["problems"]
