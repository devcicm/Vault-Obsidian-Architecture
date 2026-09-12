"""La distribución se deriva: no mantiene un catálogo paralelo."""

import pytest

from vault.meta_toolkit.distribucion import derivar_distribucion


def _projection():
    from vault_mcp_catalog import TOOLS_CATALOG
    from vault_servicio import NATURALEZAS

    return derivar_distribucion(TOOLS_CATALOG, NATURALEZAS)


def test_la_proyeccion_es_determinista_y_cubre_el_catalogo():
    from vault_mcp_catalog import TOOLS_CATALOG

    assert _projection() == _projection()
    assert set(_projection()) == set(TOOLS_CATALOG)


def test_runtime_y_meta_se_derivan_de_naturalezas_sin_lista_paralela():
    from vault_servicio import NATURALEZAS

    proyeccion = _projection()
    meta = set(NATURALEZAS["meta_estandar"]["tools"])
    assert meta
    assert all(proyeccion[nombre].clase == "maintenance" for nombre in meta)
    assert all(not proyeccion[nombre].distributable for nombre in meta)
    assert all(proyeccion[nombre].execution_module is None for nombre in proyeccion)


def test_distribuible_no_significa_que_la_operacion_instalada_ya_exista():
    """PR5 aún define alcance; el resolver instalado todavía no existe."""
    assert any(entrada.distributable for entrada in _projection().values())
    assert all(
        entrada.execution_module is None
        for entrada in _projection().values()
        if entrada.distributable
    )


def test_drift_entre_registros_falla_sin_importar_scripts_fisicos():
    with pytest.raises(ValueError, match="divergentes"):
        derivar_distribucion({"vault_x": {"script": "vault_x.py"}}, {"runtime": {"tools": []}})
