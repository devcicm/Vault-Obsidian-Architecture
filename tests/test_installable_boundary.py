"""Contrato anti-drift de la frontera instalable."""

from vault.meta_toolkit.distribucion import clasificar_tools
from vault.meta_toolkit.recursos_distribucion import clasificar_recurso, entra_al_wheel


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
