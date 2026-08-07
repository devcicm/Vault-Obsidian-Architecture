"""`vault_compact_contracts` tenía una segunda copia del catálogo, y la usaba.

Tres defectos superpuestos, los tres silenciosos:

1. `_GROUPS_HARDCODED` se había quedado en **31 grupos** frente a los 37
   canónicos. Nada lo comparaba con nada, así que la copia envejeció sola.
2. Se elegía dentro de un `except Exception` que se tragaba cualquier fallo de
   lectura del spec. Un `tool-spec.json` ilegible producía contratos sin grupo
   y sin `declared_returns` con `ok: true`.
3. `GROUPS` era una constante calculada en tiempo de import contra el vault que
   estuviera detectado entonces (AP-49), de modo que `set_vault_root()` no
   podía cambiarla: dos vaults en el mismo intérprete compartían catálogo.

La copia no se borra —no-derogación—, deja de ser fuente. La pertenencia sale
del `tool-spec.json`, que es la proyección del catálogo que
`vault_mcp_catalog --check-contracts` ya vigila.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_compact_contracts as cc  # noqa: E402
import vault_io  # noqa: E402
from vault_mcp_catalog import GROUPS as CATALOGO  # noqa: E402


def test_la_copia_local_sigue_ahi_pero_no_es_fuente():
    """No-derogación: se conserva anotada, no se usa."""
    assert cc._GROUPS_HARDCODED, "la copia no se borra, se anota"
    assert "superseded_by" in Path(cc.__file__).read_text(encoding="utf-8")


def test_la_copia_local_estaba_desfasada():
    """Es el motivo por el que dejó de ser fuente: nadie la comparaba."""
    assert len(cc._GROUPS_HARDCODED) < len(CATALOGO)


def test_la_pertenencia_coincide_con_el_catalogo():
    """Toda tool del catálogo cae en el grupo que el catálogo le da."""
    del_catalogo = {t: g for g, tools in CATALOGO.items() for t in tools}
    for tool, grupo in del_catalogo.items():
        assert cc._grupo_de(tool).get("name") == grupo, tool


def test_groups_se_resuelve_al_leerse_no_al_importarse():
    """El símbolo público se conserva; lo que cambia es cuándo se calcula."""
    from vault_compact_contracts import GROUPS

    assert len(GROUPS) == len(cc.GROUPS) > len(cc._GROUPS_HARDCODED)


def test_dos_raices_no_comparten_catalogo(tmp_path, monkeypatch):
    """Lo que el binding en import hacía imposible.

    Se le da al vault de pruebas un spec con una sola tool: si `GROUPS` se
    hubiera fijado al importar, seguiría devolviendo el del repo.
    """
    spec = tmp_path / "00_System" / "tool-spec.json"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        json.dumps(
            {
                "version": "test",
                "tools": {
                    "vault_write": {
                        "group": "Core",
                        "group_id": 1,
                        "declared_returns": ["ok"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    cc._SPEC_CACHE.clear()
    try:
        vault_io.set_vault_root(tmp_path)
        assert cc._grupos() == [
            {"id": 1, "name": "Core", "tools": ["vault_write"]}
        ]
    finally:
        vault_io.reset_vault_root()
        cc._SPEC_CACHE.clear()

    assert len(cc._grupos()) > 1, "al volver, el catálogo del repo otra vez"


def test_un_spec_ilegible_no_se_traga_en_silencio(tmp_path, monkeypatch):
    """Un contrato sin grupo no es un modo degradado, es un defecto."""
    monkeypatch.setattr(cc, "resolve_tool_spec", lambda: None)
    cc._SPEC_CACHE.clear()
    with pytest.raises(FileNotFoundError, match="tool-spec.json"):
        cc._tool_spec()
    cc._SPEC_CACHE.clear()
