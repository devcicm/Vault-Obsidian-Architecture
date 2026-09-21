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
    assert all(proyeccion[nombre].execution_module is None for nombre in meta)


def test_distribuible_no_significa_que_toda_operacion_ya_este_instalada():
    """Una sola promesa explícita no convierte el alcance entero en instalado."""
    assert any(entrada.distributable for entrada in _projection().values())
    instaladas = {
        nombre: entrada.execution_module
        for nombre, entrada in _projection().items()
        if entrada.execution_module is not None
    }
    assert instaladas == {
        "vault_query_parse": "vault.consulta.query_parse",
        "vault_knowledge_save": "vault.autoria.knowledge_save",
        "vault_knowledge_get": "vault.autoria.knowledge_get",
    }
    assert any(
        entrada.execution_module is None
        for entrada in _projection().values()
        if entrada.distributable
    )


def test_execution_module_invalido_falla_en_la_proyeccion():
    with pytest.raises(ValueError, match="execution_module inválido"):
        derivar_distribucion(
            {"vault_x": {"script": "vault_x.py", "execution_module": ""}},
            {"runtime": {"tools": ["vault_x"]}},
        )


def test_drift_entre_registros_falla_sin_importar_scripts_fisicos():
    with pytest.raises(ValueError, match="divergentes"):
        derivar_distribucion({"vault_x": {"script": "vault_x.py"}}, {"runtime": {"tools": []}})


def test_naturalezas_se_reexporta_desde_el_mismo_objeto_canonico():
    import vault_servicio
    from vault.meta_toolkit.naturalezas import NATURALEZAS

    assert vault_servicio.NATURALEZAS is NATURALEZAS
