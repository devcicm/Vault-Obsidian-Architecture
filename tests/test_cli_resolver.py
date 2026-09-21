"""El resolver no convierte adaptadores legacy en operaciones instaladas."""

import importlib
from dataclasses import replace

from cli import registry
from cli.resolver import resolve_operation
from cli.runner import build_argv
from vault.meta_toolkit.distribucion import DistribucionTool


def _fragment(module=None):
    actual = registry.resolve("vault_read")
    assert actual is not None and actual.distribution is not None
    metadata = replace(
        actual.distribution,
        execution_module=module,
    )
    return replace(actual, distribution=metadata)


def test_sin_execution_module_no_intenta_importar_instalado(monkeypatch, tmp_path):
    fragment = _fragment()
    legacy = tmp_path / fragment.script
    legacy.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "cli.resolver.importlib.util.find_spec",
        lambda _: (_ for _ in ()).throw(AssertionError("no debe buscar instalado")),
    )
    assert resolve_operation(fragment, legacy_scripts=tmp_path).kind == "legacy"


def test_modulo_estable_declarado_gana_sobre_el_adaptador_legacy(tmp_path, monkeypatch):
    module = "operacion_estable_fixture"
    stable = tmp_path / "stable"
    legacy_root = tmp_path / "legacy"
    stable.mkdir()
    legacy_root.mkdir()
    (stable / f"{module}.py").write_text(
        "def execute():\n    return None\n", encoding="utf-8"
    )
    legacy = legacy_root / "vault_read.py"
    legacy.write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(stable))
    importlib.invalidate_caches()
    target = resolve_operation(_fragment(module), legacy_scripts=legacy_root)
    assert target.kind == "installed"
    assert target.module == module


def test_modulo_declarado_pero_no_importable_no_sale_como_instalado(tmp_path):
    target = resolve_operation(_fragment("operacion_que_no_existe"), legacy_scripts=tmp_path)
    assert target.kind == "invalid"
    assert target.module == "operacion_que_no_existe"


def test_wrapper_que_importa_scripts_no_cuenta_como_operacion_estable(tmp_path, monkeypatch):
    module = "wrapper_legacy_fixture"
    stable = tmp_path / "stable"
    legacy_root = tmp_path / "legacy"
    stable.mkdir()
    legacy_root.mkdir()
    (stable / f"{module}.py").write_text(
        "from scripts import vault_read\n\ndef execute():\n    return vault_read\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(stable))
    importlib.invalidate_caches()
    target = resolve_operation(_fragment(module), legacy_scripts=legacy_root)
    assert target.kind == "invalid"
    assert target.detail == "el módulo instalado importa scripts/"


def test_fallback_legacy_conserva_el_adaptador_historico(tmp_path):
    fragment = _fragment()
    legacy = tmp_path / fragment.script
    legacy.write_text("print('legacy')\n", encoding="utf-8")
    target = resolve_operation(fragment, legacy_scripts=tmp_path)
    assert target.kind == "legacy"
    assert target.path == legacy


def test_runner_usa_menos_m_para_un_destino_instalado(tmp_path, monkeypatch):
    module = "fixture_operation"
    stable = tmp_path / "stable"; legacy = tmp_path / "legacy"
    stable.mkdir(); legacy.mkdir()
    (stable / f"{module}.py").write_text("def main(): pass\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(stable)); importlib.invalidate_caches()
    fragment = _fragment(module)
    target = resolve_operation(fragment, legacy_scripts=legacy)
    op = type("Operation", (), {"fragment": fragment, "tool": fragment.name, "args": {}})()
    assert build_argv(op, target) == [__import__("sys").executable, "-m", module]


def test_la_primera_operacion_real_declara_su_modulo_estable():
    fragment = registry.resolve("vault_query_parse")
    assert fragment is not None and fragment.distribution is not None
    target = resolve_operation(fragment, legacy_scripts=registry.SCRIPTS_DIR)
    assert target.kind == "installed"
    assert target.module == "vault.consulta.query_parse"
    op = type("Operation", (), {"fragment": fragment, "tool": fragment.name, "args": {}})()
    assert build_argv(op, target) == [
        __import__("sys").executable,
        "-m",
        "vault.consulta.query_parse",
    ]


def test_el_resolver_no_contiene_un_catalogo_manual_de_tools():
    source = (registry.Path(__file__).resolve().parent.parent / "cli" / "resolver.py").read_text(
        encoding="utf-8"
    )
    assert "vault_read" not in source
    assert "TOOLS_CATALOG" not in source
