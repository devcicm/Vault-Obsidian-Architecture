"""Contrato anti-drift de la frontera instalable."""

from vault.meta_toolkit.distribucion import clasificar_tools
from vault.meta_toolkit.recursos_distribucion import clasificar_recurso, entra_al_wheel
from cli.resolver import resolve_operation
from vault_toolkit.loading import import_toolkit_module


def _distribucion():
    from vault_mcp_catalog import TOOLS_CATALOG
    from vault_servicio import NATURALEZAS

    return clasificar_tools(TOOLS_CATALOG, NATURALEZAS)


def test_toda_tool_tiene_una_clasificacion_de_distribucion_derivada():
    from vault_mcp_catalog import TOOLS_CATALOG

    distribucion = _distribucion()
    assert set(distribucion) == set(TOOLS_CATALOG)
    assert all(d.clase in {"runtime", "maintenance"} for d in distribucion.values())


def test_meta_estandar_no_se_publica_como_operacion_runtime():
    from vault_servicio import NATURALEZAS

    distribucion = _distribucion()
    meta = set(NATURALEZAS["meta_estandar"]["tools"])
    assert meta
    assert all(not distribucion[n].distributable for n in meta)
    assert all(distribucion[n].execution_module is None for n in meta)


def test_modulo_de_ejecucion_sale_del_script_del_catalogo():
    from vault_mcp_catalog import TOOLS_CATALOG

    distribucion = _distribucion()
    for nombre, d in distribucion.items():
        if not d.distributable:
            continue
        stem = (TOOLS_CATALOG[nombre].get("script") or f"{nombre}.py").removesuffix(".py")
        assert d.execution_module == f"vault_toolkit.operations.{stem}"


def test_ownership_de_recursos_separa_runtime_toolkit_y_repo():
    casos = {
        "runtime/00_System/tool-spec.json": "runtime_operational",
        "runtime/00_System/standard-version.json": "runtime_operational",
        "scripts/vault_ontology.json": "bootstrap",
        "vault/kernel/contexto.py": "toolkit",
        "scripts/arch-baseline.json": "standard_maintenance",
        "docs/BLUEPRINT.md": "repo_only",
        "tests/fixtures/x.json": "test",
        "vault-sandbox/00_System/x.json": "test",
    }
    assert {p: clasificar_recurso(p) for p in casos} == casos
    assert entra_al_wheel("scripts/vault_ontology.json")
    assert not entra_al_wheel("scripts/arch-baseline.json")
    assert not entra_al_wheel("runtime/00_System/tool-spec.json")


def test_resolver_prefiere_modulo_instalado(monkeypatch, tmp_path):
    from cli import registry

    frag = registry.resolve("vault_read")
    monkeypatch.setattr("cli.resolver.importlib.util.find_spec", lambda _: type("Spec", (), {"origin": None})())
    target = resolve_operation(frag, legacy_scripts=tmp_path)
    assert target.kind == "installed"
    assert target.module == frag.distribution.execution_module


def test_resolver_conserva_fallback_legacy_del_checkout(monkeypatch, tmp_path):
    from cli import registry

    frag = registry.resolve("vault_read")
    script = tmp_path / frag.script
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr("cli.resolver.importlib.util.find_spec", lambda _: None)
    target = resolve_operation(frag, legacy_scripts=tmp_path)
    assert target.kind == "legacy"
    assert target.path == script


def test_resolver_reporta_operacion_ausente(monkeypatch, tmp_path):
    from cli import registry

    frag = registry.resolve("vault_read")
    monkeypatch.setattr("cli.resolver.importlib.util.find_spec", lambda _: None)
    assert resolve_operation(frag, legacy_scripts=tmp_path).kind == "missing"


def test_loader_primario_no_necesita_checkout(monkeypatch, tmp_path):
    modulo = "operacion_instalada_de_prueba"
    (tmp_path / f"{modulo}.py").write_text("VALUE = 42\n", encoding="utf-8")
    monkeypatch.syspath_prepend(tmp_path)
    sys_modules = __import__("sys").modules
    sys_modules.pop(modulo, None)
    cargado = import_toolkit_module(modulo)
    assert cargado.VALUE == 42
    assert tmp_path in __import__("pathlib").Path(cargado.__file__).parents


def test_fallback_legacy_no_deja_scripts_en_sys_path(tmp_path):
    import sys

    modulo = "operacion_legacy_de_prueba"
    (tmp_path / f"{modulo}.py").write_text("VALUE = 7\n", encoding="utf-8")
    sys.modules.pop(modulo, None)
    antes = list(sys.path)
    assert import_toolkit_module(modulo, legacy_scripts=tmp_path).VALUE == 7
    assert sys.path == antes


def test_puntos_distribuibles_no_insertan_scripts_en_sys_path():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    rutas = [
        root / "cli/registry.py",
        root / "cli/runner.py",
        root / "cli/resolver.py",
        root / "vault/kernel/adaptadores.py",
        root / "vault/autoria/frontmatter.py",
    ]
    for ruta in rutas:
        tree = ast.parse(ruta.read_text(encoding="utf-8"))
        llamadas = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "insert"
            and isinstance(n.func.value, ast.Attribute)
            and n.func.value.attr == "path"
        ]
        assert not llamadas, ruta


def test_adaptadores_de_operacion_derivan_del_catalogo():
    from vault_distribution_sync import sync

    assert sync(check=True) == 0


def test_toda_operacion_distribuible_tiene_namespace_importable():
    import importlib

    for d in _distribucion().values():
        if d.distributable:
            assert importlib.import_module(d.execution_module).main


def test_modulo_y_fallback_legacy_conservan_semantica(tmp_path):
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    runtime = tmp_path / "runtime"
    nota = runtime / "07_Knowledge" / "boundary.md"
    nota.parent.mkdir(parents=True)
    nota.write_text("---\ntitle: Boundary\ntype: knowledge\n---\n# Boundary\n", encoding="utf-8")
    env = {**os.environ, "VAULT_ROOT": str(runtime), "VAULT_VOICE": "0"}
    comandos = [
        [sys.executable, str(root / "scripts/vault_read.py"), "--path", "07_Knowledge/boundary.md"],
        [sys.executable, "-m", "vault_toolkit.operations.vault_read", "--path", "07_Knowledge/boundary.md"],
    ]
    salidas = []
    for comando in comandos:
        proc = subprocess.run(
            comando, cwd=root, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
        assert proc.returncode == 0, proc.stderr
        salidas.append(json.loads(proc.stdout))
    for salida in salidas:
        salida.pop("timestamp", None)
        salida.pop("vault_says", None)
    assert salidas[0] == salidas[1]
