"""Quien consume un envelope de error lee el mensaje por su dueño (AP-52 / AP-51).

Medido 2026-10-02: ocho sitios leían `resultado.get("error")`, la clave que el
contrato dejó de emitir cuando todo envelope pasó por construir_error. Con el
índice de búsqueda ausente, vault_context_pack recibía INDEX_NOT_FOUND, leía
None y el único aviso culpaba a la consulta («revisa la consulta o amplía
--budget») en vez de decir «Run vault_reindex first».
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def test_mensaje_de_lee_message_y_cae_a_la_clave_vieja():
    from vault_errors import emit_error, mensaje_de

    assert mensaje_de(emit_error("vault_search", "INDEX_NOT_FOUND", "falta el índice")) == "falta el índice"
    assert mensaje_de({"ok": False, "error": "forma vieja"}) == "forma vieja"
    assert mensaje_de({"ok": True}) is None


def test_ap51_context_pack_dice_que_fallo_la_busqueda(tmp_path):
    import vault_io

    root = tmp_path / "v"
    for s in ("00_System", "07_Knowledge", "99_Index"):
        (root / s).mkdir(parents=True)
    (root / "07_Knowledge" / "auth.md").write_text("---\ntitle: auth\n---\nauth\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    import vault_context_pack

    r = vault_context_pack.vault_context_pack("auth decisions")
    lexica = [w for w in r["warnings"] if w.startswith("búsqueda léxica")]
    assert lexica and "vault_reindex" in lexica[0]


def test_ningun_consumidor_lee_la_clave_error_de_un_envelope():
    """Mundo cerrado sobre los sitios medidos: `.get('error'` sobre el resultado
    de otra tool vuelve a ser None en cuanto esa tool emite por emit_error."""
    import re

    patron = re.compile(r"""\.get\(\s*["']error["']""")
    sitios = {
        "scripts/vault_change_log.py", "scripts/vault_code_tag.py",
        "scripts/vault_context_pack.py", "scripts/vault_diagram_export.py",
        "scripts/vault_folder_registry.py", "scripts/vault_move.py",
        "scripts/vault_propagate.py",
    }
    quedan = sorted(s for s in sitios if patron.search((ROOT / s).read_text(encoding="utf-8")))
    assert quedan == []
