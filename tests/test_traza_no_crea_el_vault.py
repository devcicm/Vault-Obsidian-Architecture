"""AP-36 — la traza de un error no crea el vault que no existe.

Medido el 2026-10-16 al llevar `vault_init` al catálogo de errores (AP-52):
`emit_error("…", "VAULT_NOT_FOUND", …)` con un VAULT_ROOT inexistente dejaba
creado `<raíz>/00_System/.tool-trace.json`. El envelope decía «no existe» y el
mismo envelope, al trazarse, lo desmentía: la siguiente llamada ya encontraba
el directorio. La traza es observabilidad best-effort; sin vault no se deposita.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def test_ap36_emit_error_sin_vault_no_lo_crea(tmp_path):
    import vault_errors
    import vault_io

    raiz = tmp_path / "no-existe"
    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(raiz)
    try:
        envelope = vault_errors.emit_error("t", "VAULT_NOT_FOUND", "no existe")
    finally:
        vault_io.set_vault_root(anterior)
    assert envelope["error_code"] == "VAULT_NOT_FOUND"
    assert not raiz.exists()


def test_con_vault_la_traza_se_sigue_depositando(tmp_path):
    import vault_errors
    import vault_io

    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    try:
        vault_errors.emit_error("t", "VAULT_NOT_FOUND", "no existe")
    finally:
        vault_io.set_vault_root(anterior)
    assert (tmp_path / "00_System" / ".tool-trace.json").is_file()
