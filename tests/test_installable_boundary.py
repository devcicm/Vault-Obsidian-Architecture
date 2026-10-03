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


def test_loader_primario_sin_impl_ni_legacy_import_error(monkeypatch, tmp_path):
    """Sin _impl ni legacy_scripts, import_toolkit_module raise ImportError.

    El bare import fallback se eliminó deliberadamente: resolver por sys.path
    sin más restricción da acceso a cualquier paquete en el entorno, rompiendo
    el aislamiento. El único camino válido es _impl (wheel) o legacy_scripts
    (checkout). Este test verifica que el comportamiento antiguo (bare import)
    ya no existe.
    """
    modulo = "modulo_que_no_existe_en_impl"
    import sys
    sys.modules.pop(modulo, None)
    # Sin _impl (el modulo no existe en _impl del repo) y sin legacy_scripts,
    # debe raise ImportError — no caer al import desnudo.
    try:
        import_toolkit_module(modulo, legacy_scripts=None)
        assert False, "deberia haber raised ImportError"
    except ImportError as exc:
        assert "no encontrado en _impl" in str(exc) or "no encontrado" in str(exc)


def test_fallback_legacy_conserva_scripts_en_sys_path(tmp_path):
    import sys

    modulo = "operacion_legacy_de_prueba"
    (tmp_path / f"{modulo}.py").write_text("VALUE = 7\n", encoding="utf-8")
    sys.modules.pop(modulo, None)
    antes = list(sys.path)
    assert import_toolkit_module(modulo, legacy_scripts=tmp_path).VALUE == 7
    assert sys.path[0] == str(tmp_path.resolve()), "legacy_scripts debe persistir en sys.path[0]"


#: Los únicos módulos instalables que tocan `sys.path`, cada uno con su motivo.
#: Hasta 2026-10-02 el test miraba una lista de seis ficheros escrita a mano:
#: un `sys.path.insert` en cualquier otro módulo de la wheel pasaba sin ruido.
#: Ahora el mundo es cerrado —todo `.py` de `vault/`, `vault_toolkit/` y
#: `cli/`— y lo que no está aquí falla. Esta tabla solo encoge.
SYS_PATH_DECLARADOS = {
    "cli/__main__.py": "punto de entrada de `python -m cli` en un checkout",
    "vault_toolkit/loading.py": "el cargador: pone `_impl` (o el checkout) primero",
    "vault/gobernanza/__init__.py":
        "auditoria_runtime importa vault_io/vault_lib por nombre desnudo; "
        "sale cuando esos imports pasen por el cargador",
}


def _inserta_en_sys_path(ruta) -> bool:
    import ast

    tree = ast.parse(ruta.read_text(encoding="utf-8"))
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "insert"
        and isinstance(n.func.value, ast.Attribute)
        and n.func.value.attr == "path"
        for n in ast.walk(tree)
    )


def _instalables():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for zona in ("vault", "vault_toolkit", "cli"):
        for ruta in sorted((root / zona).rglob("*.py")):
            if "__pycache__" not in ruta.parts:
                yield ruta.relative_to(root).as_posix(), ruta


def test_puntos_distribuibles_no_insertan_scripts_en_sys_path():
    insertan = {rel for rel, ruta in _instalables() if _inserta_en_sys_path(ruta)}
    assert insertan - set(SYS_PATH_DECLARADOS) == set(), "sys.path.insert nuevo en la wheel"
    # Un declarado que ya no inserta se retira de la tabla: solo encoge.
    assert set(SYS_PATH_DECLARADOS) - insertan == set()


def test_la_medida_de_sys_path_ve_un_insert_nuevo(tmp_path):
    nuevo = tmp_path / "m.py"
    nuevo.write_text("import sys\nsys.path.insert(0, 'x')\n", encoding="utf-8")
    limpio = tmp_path / "n.py"
    limpio.write_text("import sys\nprint(sys.path)\n", encoding="utf-8")
    assert _inserta_en_sys_path(nuevo)
    assert not _inserta_en_sys_path(limpio)


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


def test_todo_recurso_de_scripts_que_entra_al_wheel_esta_en_su_package_data():
    """El registro decía que `vault_ontology.json` entra a la wheel y el test de
    arriba lo confirmaba contra el propio registro (AP-44): `pyproject.toml` no
    la declaraba, la wheel salía sin ella y `vault_graph_merge` tipaba el grafo
    con una ontología vacía. Aquí se mide contra lo que lee setuptools."""
    import pytest
    from pathlib import Path

    tomllib = pytest.importorskip("tomllib")
    raiz = Path(__file__).resolve().parent.parent
    st = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]
    assert st["package-dir"]["vault_toolkit._impl"] == "scripts"
    declarados = set(st.get("package-data", {}).get("vault_toolkit._impl", []))
    deben = {
        f.name for f in (raiz / "scripts").iterdir()
        if f.is_file() and f.suffix != ".py" and entra_al_wheel(f"scripts/{f.name}")
    }
    assert "vault_ontology.json" in deben
    assert deben <= declarados, sorted(deben - declarados)
