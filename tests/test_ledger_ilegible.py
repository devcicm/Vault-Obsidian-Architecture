"""AP-51 — si el ledger de escrituras no se puede leer, la voz no dice «nada cambió».

`wrap_main` lee el ledger AP-37 en el hilo de la tool para que la voz (AP-43)
sepa si la llamada escribió. Hasta el 2026-10-16, un fallo al leerlo devolvía
`{}`, indistinguible de «cero escrituras», y la voz afirmaba «Nada cambió en mí
con esta llamada» sin haberlo comprobado. «No pude mirar» no es «no hay».
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

import vault_voice as voz  # noqa: E402


def test_la_voz_no_afirma_una_lectura_que_no_comprobo():
    d = voz.speak("vault_write", {"ok": True}, {"ledger_ilegible": "RuntimeError: x"})
    assert d["moment"] == "unknown"
    assert "Nada cambió" not in d["message"]
    assert "no sé" in d["message"]


def callback_ledger_ilegible():
    import vault_ledger

    def broken():
        raise RuntimeError("ledger roto")

    vault_ledger.write_report = broken
    print(json.dumps({"ok": True}))
    return 0


def test_wrap_main_publica_el_ledger_ilegible(monkeypatch, capsys):
    import vault_errors

    monkeypatch.delenv("VAULT_VOICE", raising=False)
    monkeypatch.setattr(sys, "argv", ["vault_audit"])
    rc = vault_errors.wrap_main(callback_ledger_ilegible, "vault_audit")
    assert rc == 0
    salida = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert salida["vault_says"]["moment"] == "unknown", salida["vault_says"]


@pytest.mark.parametrize("operation", ["write_ledger_reset", "write_report"])
def test_worker_reports_unknown_ledger_without_logging_private_error(monkeypatch, capsys, operation):
    import vault_errors
    import vault_ledger

    def broken():
        raise RuntimeError("PRIVATE-LEDGER-CANARY")

    def unexpected_trace(*args, **kwargs):
        pytest.fail("Ledger degradation must not create an error trace")

    monkeypatch.delenv("VAULT_VOICE", raising=False)
    monkeypatch.setattr(vault_ledger, operation, broken)
    monkeypatch.setattr(vault_errors, "emit_error", unexpected_trace)
    # Exercise the worker entry directly so the injected failure is inside
    # its process boundary, rather than a parent-only monkeypatch.
    assert vault_errors._wrap_main_local(lambda: print('{"ok": true}'), "vault_audit") == 0
    output = capsys.readouterr().out
    assert "PRIVATE-LEDGER-CANARY" not in output
    assert json.loads(output)["vault_says"]["moment"] == "unknown"
