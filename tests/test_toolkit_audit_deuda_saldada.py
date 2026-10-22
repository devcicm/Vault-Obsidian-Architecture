"""La deuda congelada del barrido del toolkit está saldada (v41.14).

La primera corrida del auditor (v41.12) dejó un DEFECTO congelado:
`vault_changelog_check`. No era un defecto de la tool —era **la línea de
release en curso**: el changelog publicaba `git: pending` de una versión que
todavía no era la vigente, y el check trata eso como error hasta que
`--fijar-hash` la cierra.

Dos cosas se comprueban aquí:

1. La baseline del auditor está **vacía**: congelar el reloj no es congelar un
   defecto, y la baseline solo puede encoger.
2. El plano declara esa deuda **saldada**, con la versión que la cerró. Una
   deuda que se salda no se borra: pasa a `saldada` (capa 7), porque una
   entrada borrada no se distingue de una que nadie volvió a mirar.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))


def test_la_deuda_del_barrido_esta_saldada():
    import vault_blueprint

    baseline = json.loads(
        (ROOT / "scripts" / "toolkit-audit-baseline.json").read_text(encoding="utf-8")
    )
    assert baseline.get("failing") == [], (
        "la baseline del barrido tiene deuda congelada: "
        f"{baseline.get('failing')}. Congelar el release en curso no es un "
        "defecto; si aparece deuda nueva, se registra en el plano."
    )

    deuda = next(
        (d for d in vault_blueprint.DEUDA_DECLARADA
         if d["id"] == "barrido_del_toolkit_con_deuda_congelada"),
        None,
    )
    assert deuda is not None, "la deuda del barrido no está declarada en el plano"
    assert deuda["estado"] == "saldada", deuda
    # La versión que la cerró es una versión **histórica**: se escribe, y por
    # eso aguanta los bumps. (La regla de `test_version_coherence` veta el
    # literal de la versión *corriente* en la suite, no el de una cerrada.)
    assert deuda["saldada_en"] == "v41.14", deuda


def test_la_version_que_saldo_la_deuda_existe_en_el_changelog():
    """La versión que cerró la deuda tiene que poder citarse (AP-53: la
    afirmación se contrasta contra el documento que la sostiene)."""
    manifiesto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    assert "### v41.14 —" in manifiesto, "el changelog no publica la versión que saldó la deuda"
