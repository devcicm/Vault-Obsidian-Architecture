"""A second onboarding does not claim it created what already existed (brownfield BF-03).

Measured on 2026-11-19 onboarding this repository twice: the second envelope
said "sin escrituras: 0 creadas y 0 fusionadas" in `indexes_skipped` and, in the
same envelope, listed the 16 notes under `created`. An agent reading `created`
believed it wrote 16 notes (AP-37). `created` now lists what was created, merged
or (in a dry run) planned; what was left as it was goes to `unchanged`.
"""

from test_onboard_escalonado import PROYECTO, _onboard, proyecto, vault  # noqa: F401


def _rutas(mapa):
    """The onboarded note paths in an envelope map (section indexes are not notes)."""
    salida = []
    for clave, valor in (mapa or {}).items():
        if clave.startswith("indexes"):
            continue
        if isinstance(valor, str) and valor.endswith(".md"):
            salida.append(valor)
        elif isinstance(valor, list):
            salida += [v for v in valor if isinstance(v, str) and v.endswith(".md")]
    return salida


def test_la_segunda_corrida_no_dice_que_creo_lo_que_ya_estaba(vault, proyecto):
    v, primera = vault
    assert _rutas(primera["created"]), "the first run must create notes"
    segunda = _onboard(v, proyecto)
    assert segunda["merge_stats"]["created"] == 0 and segunda["merge_stats"]["merged"] == 0
    assert _rutas(segunda["created"]) == [], segunda["created"]
    assert sorted(_rutas(segunda["unchanged"])) == sorted(_rutas(primera["created"]))
