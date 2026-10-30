"""D-07 — limite declarado: una ronda de trabajo no tiene contenedor.

El estudio pide un `session-log` por ronda con `round_id:` en 04_Sessions y que
las notas de la ronda lo lleven. Hoy ni el contrato de nota ni ninguna tool
activa declaran `round_id`; declararlo sin quien lo escriba seria inventarlo.
Este test fija el hueco y falla el dia que se cierre, para que
`vault_blueprint.DEUDA_DECLARADA` pase a `saldada`.
"""
from pathlib import Path

from vault.kernel.contrato_nota import CAMPOS

ROOT = Path(__file__).resolve().parent.parent


def test_limite_declarado_round_id_no_existe_en_el_contrato():
    assert "round_id" not in CAMPOS, "ya se declara: salda la deuda D-07"
    escritores = [p.name for p in (ROOT / "scripts").glob("vault_*.py")
                  if p.name != "vault_blueprint.py"  # ahi se declara la deuda
                  and "round_id" in p.read_text(encoding="utf-8", errors="replace")]
    assert escritores == [], f"{escritores} ya escriben round_id: salda la deuda D-07"
