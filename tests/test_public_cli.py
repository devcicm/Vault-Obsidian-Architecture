"""Contrato del MVP público instalado, sin importar adaptadores de checkout."""

from __future__ import annotations

import ast
import json
from importlib import resources
from pathlib import Path

import pytest

from vault import product_cli
from vault.kernel.errores import ERROR_CATALOG, construir_error
from vault.meta_toolkit import resolucion_producto
from vault.meta_toolkit.catalogo_producto import catalogo_producto


def _version(monkeypatch) -> None:
    monkeypatch.setattr(product_cli.metadata, "version", lambda _: "40.34")


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def _error(capsys):
    return json.loads(capsys.readouterr().err)


def test_version_usa_la_metadata_de_la_distribucion(monkeypatch):
    _version(monkeypatch)
    assert product_cli.toolkit_version() == "40.34"


def _runtime_sin_modulo() -> str:
    """Una tool runtime que el catálogo declara sin implementación instalada.

    Se elige del catálogo y no se escribe a mano: hasta A2 era ``vault_read``, y
    los tests que la nombraban quedaron rojos al instalarse (AP-47).
    """
    candidatas = sorted(
        name for name, tool in catalogo_producto().items()
        if tool.clase == "runtime" and tool.execution_module is None
    )
    if not candidatas:
        pytest.skip("el catálogo ya no declara ninguna tool runtime sin instalar")
    return candidatas[0]


def test_tools_list_sale_de_la_proyeccion_derivada(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["tools", "list"]) == 0
    payload = _json(capsys)
    by_name = {entry["name"]: entry for entry in payload["tools"]}
    catalogo = catalogo_producto()
    assert set(by_name) == set(catalogo)
    # La CLI dice «instalada» exactamente cuando la resolución lo confirma.
    for name, entry in by_name.items():
        estado = resolucion_producto.resolver_producto(name).estado
        assert entry["installed"] is (estado == resolucion_producto.INSTALLED), name
        assert entry["class"] == catalogo[name].clase, name
    assert by_name["vault_query_parse"] == {
        "name": "vault_query_parse", "class": "runtime", "installed": True,
    }
    assert by_name[_runtime_sin_modulo()]["installed"] is False
    assert by_name["vault_arch"] == {
        "name": "vault_arch", "class": "maintenance", "installed": False,
    }


def test_tools_show_distingue_instalada_no_instalada_y_mantenimiento(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["tools", "show", "vault_query_parse"]) == 0
    installed = _json(capsys)
    assert installed["installed"] is True
    assert installed["execution_module"] == "vault_toolkit.operations.vault_query_parse"

    assert product_cli.main(["tools", "show", _runtime_sin_modulo()]) == 0
    legacy = _json(capsys)
    assert legacy["runtime_operation"] is True
    assert legacy["installed"] is False

    assert product_cli.main(["tools", "show", "vault_arch"]) == 0
    maintenance = _json(capsys)
    assert maintenance["runtime_operation"] is False
    assert maintenance["installed"] is False


def test_tools_show_publica_los_parametros(monkeypatch, capsys):
    """Medido el 2026-10-05: `tools show` decía si la tool estaba instalada pero
    no qué argumentos aceptaba, y había que abrir el catálogo o el `--help` del
    script para saber cómo llamarla. Salen del `inputSchema` empaquetado, el
    mismo que valida el servidor MCP."""
    _version(monkeypatch)
    assert product_cli.main(["tools", "show", "vault_append"]) == 0
    datos = _json(capsys)
    assert datos["description"]
    assert datos["group"]
    por_nombre = {p["name"]: p for p in datos["parameters"]}
    assert por_nombre["path"]["required"] is True
    assert por_nombre["path"]["type"] == "string"
    assert por_nombre["section"]["required"] is False
    assert por_nombre["no-timestamp"]["type"] == "boolean"
    assert all(p["description"] for p in datos["parameters"])


def test_tools_show_desconocida_es_controlada(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["tools", "show", "definitely_not_a_real_tool"]) == 3
    assert _error(capsys)["state"] == resolucion_producto.UNKNOWN_TOOL


def test_error_publico_sale_del_contrato_estable(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["run", "definitely_not_a_real_tool"]) == 3
    payload = _error(capsys)
    assert payload["error_code"] == "INVALID_ACTION"
    # La `action` es la del catálogo, que es por la que decide el consumidor;
    # la pista es la del sitio, que sabe por qué no se ejecutó (v40.34).
    catalogo = construir_error("vault", "INVALID_ACTION")["recovery"]
    assert payload["recovery"]["action"] == catalogo["action"]
    assert payload["recovery"]["hint"] == product_cli._PISTAS_DE_RESOLUCION[
        resolucion_producto.UNKNOWN_TOOL]
    assert payload["state"] == resolucion_producto.UNKNOWN_TOOL


def test_error_publico_delega_en_el_owner_estable(monkeypatch, capsys):
    _version(monkeypatch)
    received = {}

    def construir(tool, code, message=None, **kwargs):
        received.update(tool=tool, code=code, message=message, **kwargs)
        return {
            "ok": False,
            "tool": tool,
            "error_code": code,
            "category": "contract",
            "severity": "error",
            "message": message,
            "recovery": "use the stable contract",
            "timestamp": "stable-owner",
            **kwargs["extra"],
        }

    monkeypatch.setattr(product_cli, "construir_error", construir)
    assert product_cli.main(["run", "definitely_not_a_real_tool"]) == 3
    assert received == {
        "tool": "vault",
        "code": "INVALID_ACTION",
        "message": "tool desconocida: definitely_not_a_real_tool",
        "extra": {
            "state": resolucion_producto.UNKNOWN_TOOL,
            "error": "tool desconocida: definitely_not_a_real_tool",
        },
        "pista": product_cli._PISTAS_DE_RESOLUCION[resolucion_producto.UNKNOWN_TOOL],
    }
    assert _error(capsys)["timestamp"] == "stable-owner"


def test_run_installed_ejecuta_python_m_sin_scripts(monkeypatch):
    _version(monkeypatch)
    received = {}

    class Process:
        returncode = 0

    def run(argv):
        received["argv"] = argv
        return Process()

    monkeypatch.setattr(product_cli.subprocess, "run", run)
    assert product_cli.main([
        "run", "vault_query_parse", "--query", "que decidimos sobre el transporte MCP", "--plan-only",
    ]) == 0
    assert received["argv"][:3] == [product_cli.sys.executable, "-m", "vault_toolkit.operations.vault_query_parse"]


@pytest.mark.parametrize(("tool", "code", "state"), [
    (None, 4, resolucion_producto.KNOWN_NOT_INSTALLED),
    ("vault_arch", 5, resolucion_producto.NOT_RUNTIME_OPERATION),
    ("definitely_not_a_real_tool", 3, resolucion_producto.UNKNOWN_TOOL),
])
def test_run_rechaza_estados_no_instalados_sin_fallback(monkeypatch, capsys, tool, code, state):
    _version(monkeypatch)
    tool = tool or _runtime_sin_modulo()
    assert product_cli.main(["run", tool]) == code
    assert _error(capsys)["state"] == state


def test_run_con_promesa_invalida_no_hace_fallback(monkeypatch, capsys):
    _version(monkeypatch)
    monkeypatch.setattr(
        product_cli,
        "resolver_producto",
        lambda _: resolucion_producto.ResolucionProducto(
            resolucion_producto.INVALID_INSTALLED_TARGET, detail="módulo no resoluble"
        ),
    )
    assert product_cli.main(["run", "vault_query_parse"]) == 6
    assert _error(capsys)["state"] == resolucion_producto.INVALID_INSTALLED_TARGET


def test_catalogo_empaquetado_es_proyeccion_del_catalogo_mcp():
    root = Path(__file__).resolve().parents[1]
    mcp = json.loads((root / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    resource = resources.files("vault.meta_toolkit").joinpath("tools-catalog.json")
    assert json.loads(resource.read_text(encoding="utf-8")) == mcp


def test_las_operaciones_instaladas_salen_del_catalogo_y_no_de_otra_tabla_manual():
    """Invariantes en vez de una tabla copiada: la tabla envejecía con cada A-n."""
    catalogo = catalogo_producto()
    installed = {
        name: tool.execution_module
        for name, tool in catalogo.items()
        if tool.execution_module is not None
    }
    # Mantenimiento nunca se instala; toda promesa de instalación resuelve.
    assert all(catalogo[name].clase == "runtime" for name in installed)
    for name in installed:
        assert (
            resolucion_producto.resolver_producto(name).estado
            == resolucion_producto.INSTALLED
        ), name
    # Las cuatro promesas históricas siguen en pie con su destino declarado.
    assert {
        "vault_query_parse": "vault_toolkit.operations.vault_query_parse",
        "vault_knowledge_save": "vault_toolkit.operations.vault_knowledge_save",
        "vault_knowledge_get": "vault_toolkit.operations.vault_knowledge_get",
        "vault_gobernanza": "vault.gobernanza.tool",
    }.items() <= installed.items()


def test_superficie_publica_no_importa_checkout_ni_scripts():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "vault/product_cli.py",
        "vault/meta_toolkit/catalogo_producto.py",
        "vault/meta_toolkit/resolucion_producto.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name == "scripts" or name.startswith("scripts.") for name in imports)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert {"REPO_ROOT", "SCRIPTS_DIR"}.isdisjoint(names)


def test_el_adaptador_legacy_reexporta_el_mismo_contrato_estable():
    import vault_errors_catalog

    assert vault_errors_catalog.ERROR_CATALOG is ERROR_CATALOG


def test_python_m_vault_es_la_misma_cli():
    """Sin `Scripts/` en el PATH, `python -m vault` es la única entrada fiable."""
    import subprocess
    import sys

    raiz = Path(__file__).resolve().parent.parent
    proceso = subprocess.run(
        [sys.executable, "-m", "vault", "tools", "show", "vault_query_parse"],
        cwd=str(raiz), capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert proceso.returncode == 0, proceso.stderr
    assert json.loads(proceso.stdout)["name"] == "vault_query_parse"


def test_python_m_product_cli_ejecuta_la_cli():
    """AP-37: `python -m vault.product_cli` salía con rc=0 sin hacer nada."""
    import subprocess
    import sys

    raiz = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "vault.product_cli", "--version"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(raiz), timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), "python -m vault.product_cli no hizo nada"
