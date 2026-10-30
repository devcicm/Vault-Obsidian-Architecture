"""B-04 — límite declarado: el colector de QG no lo ejecuta ninguna puerta.

`audits/fase2/colector_qg.py` es quien emite los recibos de QG-00..06, pero
ni `vault_gate.PUERTAS` ni ningún workflow lo invocan: re-verificar el
candidato exige correrlo a mano en un checkout exacto del `product_sha`
(medido: sobre un descendiente documental devuelve QG-00 BLOCKED por
CHECKOUT_EN_OTRO_SHA, así que `release.yml` no puede llamarlo tal cual).
Este test fija el hueco y falla el día que alguien lo cablee: entonces la
deuda `colector_qg_fuera_de_toda_puerta` pasa a `saldada`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_limite_declarado_colector_qg_fuera_de_toda_puerta():
    ficheros = list((ROOT / ".github" / "workflows").glob("*.yml"))
    ficheros.append(ROOT / "scripts" / "vault_gate.py")
    citan = [f.name for f in ficheros if "colector_qg" in f.read_text(encoding="utf-8")]
    assert citan == [], f"el colector ya esta cableado en {citan}: salda la deuda"
