"""Vertical de memoria estable: Markdown primero, checkout nunca."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from vault.autoria.conocimiento import guardar_conocimiento, recuperar_conocimiento
from vault.ciclo_de_vida.producto import inicializar_runtime
from vault.meta_toolkit.catalogo_producto import catalogo_producto
from vault.meta_toolkit.resolucion_producto import INSTALLED, resolver_producto


ROOT = Path(__file__).resolve().parents[1]


def _runtime(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    assert inicializar_runtime(root)["ok"]
    return root


def test_write_y_recovery_usan_el_markdown_como_autoridad(tmp_path):
    root = _runtime(tmp_path)
    canary = "MEMORY_CANARY_UNIT_7f3a"
    assert recuperar_conocimiento(root, canary)["total"] == 0
    saved = guardar_conocimiento(root, "concept", canary, f"Decisión {canary}: Boreal-17.")
    assert saved["ok"]
    note = root / saved["path"]
    assert note.is_file()
    assert canary in note.read_text(encoding="utf-8")
    recovered = recuperar_conocimiento(root, canary)
    assert recovered["total"] == 1
    assert canary in recovered["topContent"]


def test_write_rechaza_runtime_inexistente_sin_dejar_archivos(tmp_path):
    target = tmp_path / "absent"
    result = guardar_conocimiento(target, "concept", "x", "contenido")
    assert result["ok"] is False
    assert not target.exists()


def test_las_tres_promesas_instaladas_salen_del_catalogo_canonico():
    expected = {
        "vault_query_parse": "vault_toolkit.operations.vault_query_parse",
        "vault_knowledge_save": "vault_toolkit.operations.vault_knowledge_save",
        "vault_knowledge_get": "vault_toolkit.operations.vault_knowledge_get",
    }
    installed = {name: tool.execution_module for name, tool in catalogo_producto().items()
                 if tool.execution_module is not None}
    assert installed == expected
    for name in expected:
        assert resolver_producto(name).estado == INSTALLED


def test_implementacion_estable_no_importa_el_checkout_ni_scripts():
    for relative in ("vault/kernel/escritura.py", "vault/autoria/conocimiento.py", "vault/autoria/knowledge_save.py", "vault/autoria/knowledge_get.py", "vault/product_cli.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name == "scripts" or name.startswith("scripts.") for name in imports)
        assert "sys.path" not in source
        assert "REPO_ROOT" not in source
        assert "runpy" not in source


def test_adaptadores_legacy_delegan_hacia_el_owner_estable():
    for script in ("vault_knowledge_save.py", "vault_knowledge_get.py"):
        source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "vault.autoria.conocimiento" in source


def test_el_mecanismo_atomico_es_un_primitive_compartido_y_no_otro_write_path():
    stable = (ROOT / "vault" / "autoria" / "conocimiento.py").read_text(encoding="utf-8")
    primitive = (ROOT / "vault" / "kernel" / "escritura.py").read_text(encoding="utf-8")
    legacy_fs = (ROOT / "scripts" / "vault_fs.py").read_text(encoding="utf-8")
    legacy_adapter = (ROOT / "scripts" / "vault_knowledge_save.py").read_text(
        encoding="utf-8"
    )
    assert "from ..kernel.escritura import escritura_atomica" in stable
    assert "escritura_atomica(path, text, encoding=\"utf-8\")" in stable
    assert not any(token in stable for token in ("mkstemp", "os.replace", "os.fsync"))
    assert "def escritura_atomica(" in primitive
    assert "def _stable_escritura_module" in legacy_fs
    assert 'import_module("vault.kernel.escritura")' in legacy_fs
    assert "writer=atomic_write_text, report=write_report" in legacy_adapter


def test_vault_fs_no_redefine_el_primitive_atomico_estable():
    legacy_fs = ROOT / "scripts" / "vault_fs.py"
    names = {
        node.name
        for node in ast.walk(ast.parse(legacy_fs.read_text(encoding="utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not names & {"escritura_atomica", "_escribir_temporal", "_fsync_si_procede"}


def test_vault_fs_reexporta_la_misma_funcion_atomica_del_owner_estable():
    spec = importlib.util.spec_from_file_location("vault_fs_for_test", ROOT / "scripts" / "vault_fs.py")
    assert spec and spec.loader
    legacy_fs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy_fs)
    from vault.kernel import escritura

    assert legacy_fs.escritura_atomica is escritura.escritura_atomica
    assert legacy_fs._escribir_temporal is escritura._escribir_temporal
    assert legacy_fs._fsync_si_procede is escritura._fsync_si_procede
