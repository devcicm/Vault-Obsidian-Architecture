"""D-07 — la ronda de trabajo tiene contenedor (saldada en v41.26).

Hasta v41.26 este test fijaba el hueco: ni el contrato de nota ni ninguna tool
activa declaraban `round_id`. Ahora `vault_ronda` abre y cierra la ronda, el
contrato declara el campo y `vault_write` lo estampa mientras está abierta; el
comportamiento lo mide `test_vault_ronda.py`. Aquí queda lo que la deuda
`ronda_sin_contenedor_round_id` decía que faltaba, para que no vuelva a faltar.
"""
from apoyo import ROOT

from vault.kernel.contrato_nota import CAMPOS


def test_round_id_tiene_contrato_y_quien_lo_escribe():
    assert CAMPOS["round_id"]["nivel"] == "opcional"
    escritores = {p.name for p in (ROOT / "scripts").glob("vault_*.py")
                  if "round_id" in p.read_text(encoding="utf-8", errors="replace")}
    assert {"vault_ronda.py", "vault_write.py"} <= escritores, sorted(escritores)
