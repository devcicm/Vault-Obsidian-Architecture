"""TDD: inventario seccionado de módulos de test y markers automáticos por propósito.

Permite correr pruebas parte por parte (`pytest -m mcp`, `pytest -m seguridad`,
`pytest -m "escritura and not slow"`) sin tocar los 643 archivos de test ni
renunciar a `pytest tests/` como corrida completa única.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from apoyo import ROOT


def test_cada_modulo_de_tests_tiene_un_bloque_canonico():
    from vault.meta_toolkit.estandar import inventario_tests as inv

    assert len(inv.BLOQUES) >= 10
    modulos = sorted(p.stem for p in (ROOT / "tests").glob("test_*.py"))
    assert len(modulos) > 500
    for mod in modulos:
        bloque = inv.clasificar_modulo(mod)
        assert bloque in inv.BLOQUES, f"{mod} -> {bloque}"


def test_bloques_clave_aislan_sus_modulos():
    from vault.meta_toolkit.estandar import inventario_tests as inv

    assert inv.clasificar_modulo("test_mcp_http_seguridad") == "mcp"
    assert inv.clasificar_modulo("test_portabilidad_terceros") == "cli"
    assert inv.clasificar_modulo("test_vault_containment") == "seguridad"
    assert inv.clasificar_modulo("test_vault_write") == "escritura"
    assert inv.clasificar_modulo("test_vault_search") == "consulta"
    assert inv.clasificar_modulo("test_vault_onboard") == "ciclo_vida"
    assert inv.clasificar_modulo("test_vault_reindex") == "grafo"
    assert inv.clasificar_modulo("test_flujo_requisitos") == "flujos"
    assert inv.clasificar_modulo("test_iso_15489_conservacion") == "iso"
    assert inv.clasificar_modulo("test_vault_gate") == "estandar"


def test_pyproject_declara_todos_los_markers_de_bloques():
    from vault.meta_toolkit.estandar import inventario_tests as inv

    texto = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for bloque in inv.BLOQUES:
        assert f'"{bloque}:' in texto, (
            f"El marker '{bloque}' falta en pyproject.toml [tool.pytest.ini_options].markers"
        )


def test_resumen_inventario_cubre_todos_los_modulos_y_segundos():
    from vault.meta_toolkit.estandar import inventario_tests as inv

    resumen = inv.resumen_inventario()
    assert resumen["ok"] is True
    assert resumen["modulos_total"] == len(list((ROOT / "tests").glob("test_*.py")))
    assert sum(b["modulos"] for b in resumen["bloques"].values()) == resumen["modulos_total"]
    assert resumen["bloques"]["mcp"]["modulos"] >= 25


def test_conftest_asigna_marker_de_bloque_sin_romper_slow(monkeypatch):
    import conftest

    # En CI con VAULT_SHARD=2/2 el hook filtraría items; aislamos el test del entorno.
    monkeypatch.delenv("VAULT_SHARD", raising=False)

    class _Item:
        def __init__(self, nodeid: str) -> None:
            self.nodeid = nodeid
            self.markers = []

        def add_marker(self, m) -> None:
            self.markers.append(m.name)

    items = [
        _Item("tests/test_mcp_http_seguridad.py::test_ejemplo"),
        _Item("tests/test_vault_write.py::test_ejemplo"),
    ]
    cfg = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=lambda **kw: None))
    conftest.pytest_collection_modifyitems(cfg, items)
    assert "mcp" in items[0].markers
    assert "escritura" in items[1].markers
