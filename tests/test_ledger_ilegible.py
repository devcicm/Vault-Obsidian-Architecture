"""AP-51 — si el ledger de escrituras no se puede leer, la voz no dice «nada cambió».

`wrap_main` lee el ledger AP-37 en el hilo de la tool para que la voz (AP-43)
sepa si la llamada escribió. Hasta el 2026-10-16, un fallo al leerlo devolvía
`{}`, indistinguible de «cero escrituras», y la voz afirmaba «Nada cambió en mí
con esta llamada» sin haberlo comprobado. «No pude mirar» no es «no hay».
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_voice as voz  # noqa: E402


def test_la_voz_no_afirma_una_lectura_que_no_comprobo():
    d = voz.speak("vault_write", {"ok": True}, {"ledger_ilegible": "RuntimeError: x"})
    assert d["moment"] == "unknown"
    assert "Nada cambió" not in d["message"]
    assert "no sé" in d["message"]


def test_wrap_main_publica_el_ledger_ilegible(monkeypatch, capsys):
    import vault_errors
    import vault_ledger

    def _roto():
        raise RuntimeError("ledger roto")

    monkeypatch.setattr(vault_ledger, "write_report", _roto)
    monkeypatch.delenv("VAULT_VOICE", raising=False)
    monkeypatch.setattr(sys, "argv", ["vault_audit"])
    rc = vault_errors.wrap_main(lambda: print(json.dumps({"ok": True})) or 0, "vault_audit")
    assert rc == 0
    salida = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert salida["vault_says"]["moment"] == "unknown", salida["vault_says"]
