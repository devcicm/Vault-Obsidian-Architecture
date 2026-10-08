"""AP-51 en el descubrimiento de vaults del servidor MCP.

Medido el 2026-10-08: `countMdFiles` se tragaba el fallo de `readdir` con
`catch (_) {}`, así que un vault con un directorio que no se podía listar
se registraba con menos notas de las que tiene y nada lo decía. Un recuento
parcial publicado como total es un dato falso sobre el vault del usuario.
"""

import json

from test_backup_base64 import _ilegible
from test_mcp_runner import SesionMCP, _init_vault


def _registro(vault_por_defecto, raiz_de_busqueda):
    s = SesionMCP(vault_por_defecto, {"VAULT_SCAN_ROOTS": str(raiz_de_busqueda)})
    try:
        r = s.llamar("vault_registry", {})
    finally:
        s.cerrar()
    return json.loads(r["result"]["content"][0]["text"])


def test_un_recuento_parcial_de_notas_se_declara(tmp_path):
    por_defecto = _init_vault(tmp_path / "defecto")
    busqueda = tmp_path / "busqueda"
    descubierto = busqueda / "vault-ajeno"
    for s in ("00_System", "99_Index", "07_Knowledge"):
        (descubierto / s).mkdir(parents=True)
    (descubierto / "07_Knowledge" / "visible.md").write_text("# V\n", encoding="utf-8")
    cerrado = descubierto / "07_Knowledge" / "cerrado"
    cerrado.mkdir()
    (cerrado / "oculta.md").write_text("# O\n", encoding="utf-8")

    with _ilegible(cerrado):
        env = _registro(por_defecto, busqueda)
    vault = next(v for v in env["vaults"] if v["name"] == "vault-ajeno")
    assert vault["notes"] == 1
    assert vault.get("notes_incomplete") == 1, vault


def test_un_recuento_completo_no_lleva_la_marca(tmp_path):
    por_defecto = _init_vault(tmp_path / "defecto")
    descubierto = tmp_path / "busqueda" / "vault-ajeno"
    for s in ("00_System", "99_Index", "07_Knowledge"):
        (descubierto / s).mkdir(parents=True)
    env = _registro(por_defecto, tmp_path / "busqueda")
    vault = next(v for v in env["vaults"] if v["name"] == "vault-ajeno")
    assert "notes_incomplete" not in vault
