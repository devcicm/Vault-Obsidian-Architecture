"""B-04 — límite declarado: el colector de QG está cableado y nunca ha corrido en la CI.

Hasta la rama `reestructura/teseo` este test fijaba que ni `vault_gate.PUERTAS`
ni ningún workflow invocaban `audits/fase2/colector_qg.py` (deuda
`colector_qg_fuera_de_toda_puerta`, ya saldada). El job `qg-receipts` de
`release.yml` lo cablea —su forma la mide `test_release_qg_receipts.py`—, pero
que un job escrito funcione solo lo dice una corrida real, y sin push la CI no
se ejecuta. Los recibos que lleva el manifiesto siguen siendo de corridas a mano.

El test falla el día que se versione un recibo de procedencia escrito por ese
job: entonces la deuda `colector_qg_sin_primera_corrida` pasa a `saldada`.
"""
import json

from apoyo import ROOT

FIRMA_DEL_JOB = "qg-receipts"


def test_limite_declarado_colector_qg_sin_primera_corrida():
    recibos = sorted((ROOT / "audits" / "fase2").glob("recibos-*/*.procedencia.json"))
    assert recibos, "sin ningún recibo de procedencia el límite no se puede medir"
    de_la_ci = [r.parent.name for r in recibos
                if FIRMA_DEL_JOB in json.loads(r.read_text(encoding="utf-8")).get("nota", "")]
    assert de_la_ci == [], f"{de_la_ci} los emitió la CI: salda la deuda"
