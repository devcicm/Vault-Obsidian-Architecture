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


def test_tools_list_sale_de_la_proyeccion_derivada(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["tools", "list"]) == 0
    payload = _json(capsys)
    by_name = {entry["name"]: entry for entry in payload["tools"]}
    assert len(by_name) == 116
    assert by_name["vault_query_parse"] == {
        "name": "vault_query_parse", "class": "runtime", "installed": True,
    }
    assert by_name["vault_read"]["installed"] is False
    assert by_name["vault_arch"] == {
        "name": "vault_arch", "class": "maintenance", "installed": False,
    }


def test_tools_show_distingue_instalada_legacy_y_mantenimiento(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["tools", "show", "vault_query_parse"]) == 0
    installed = _json(capsys)
    assert installed["installed"] is True
    assert installed["execution_module"] == "vault.consulta.query_parse"

    assert product_cli.main(["tools", "show", "vault_read"]) == 0
    legacy = _json(capsys)
    assert legacy["runtime_operation"] is True
    assert legacy["installed"] is False

    assert product_cli.main(["tools", "show", "vault_arch"]) == 0
    maintenance = _json(capsys)
    assert maintenance["runtime_operation"] is False
    assert maintenance["installed"] is False


def test_tools_show_desconocida_es_controlada(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["tools", "show", "definitely_not_a_real_tool"]) == 3
    assert _error(capsys)["state"] == resolucion_producto.UNKNOWN_TOOL


def test_error_publico_sale_del_contrato_estable(monkeypatch, capsys):
    _version(monkeypatch)
    assert product_cli.main(["run", "definitely_not_a_real_tool"]) == 3
    payload = _error(capsys)
    assert payload["error_code"] == "INVALID_ACTION"
    assert payload["recovery"] == construir_error("vault", "INVALID_ACTION")["recovery"]
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
    assert received["argv"][:3] == [product_cli.sys.executable, "-m", "vault.consulta.query_parse"]


@pytest.mark.parametrize(("tool", "code", "state"), [
    ("vault_read", 4, resolucion_producto.KNOWN_NOT_INSTALLED),
    ("vault_arch", 5, resolucion_producto.NOT_RUNTIME_OPERATION),
    ("definitely_not_a_real_tool", 3, resolucion_producto.UNKNOWN_TOOL),
])
def test_run_rechaza_estados_no_instalados_sin_fallback(monkeypatch, capsys, tool, code, state):
    _version(monkeypatch)
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


def test_exactamente_una_operacion_instalada_y_no_hay_otra_tabla_manual():
    installed = {
        name: tool.execution_module
        for name, tool in catalogo_producto().items()
        if tool.execution_module is not None
    }
    assert installed == {"vault_query_parse": "vault.consulta.query_parse"}


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
