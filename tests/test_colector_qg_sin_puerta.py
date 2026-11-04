"""B-04 — el colector de QG está cableado **y ya corrió de verdad en la CI**.

Hasta la rama `reestructura/teseo` este test fijaba que ni `vault_gate.PUERTAS`
ni ningún workflow invocaban `audits/fase2/colector_qg.py` (deuda
`colector_qg_fuera_de_toda_puerta`, ya saldada). El job `qg-receipts` de
`release.yml` lo cablea —su forma la mide `test_release_qg_receipts.py`—, pero
que un job escrito funcione solo lo decía una corrida real, y sin push la CI no
se ejecuta.

**Saldo el 2026-11-03** con la publicación de v41.26: el job corrió (run
41744360675, tag v41.26), dio QG-00..QG-07 PASS, y su recibo de procedencia de
la suite quedó versionado en `audits/fase2/recibos-R27-9ac330a-ci/`. Este test
pasó de exigir que la deuda estuviera abierta a exigir que **siga cerrada**: si
alguien borra ese recibo, la deuda vuelve a estar abierta y el test lo dice.
"""
import json

from apoyo import ROOT

FIRMA_DEL_JOB = "qg-receipts"


def test_limite_declarado_colector_qg_sin_primera_corrida():
    recibos = sorted((ROOT / "audits" / "fase2").glob("recibos-*/*.procedencia.json"))
    assert recibos, "sin ningún recibo de procedencia el límite no se puede medir"
    de_la_ci = [r.parent.name for r in recibos
                if FIRMA_DEL_JOB in json.loads(r.read_text(encoding="utf-8")).get("nota", "")]
    assert de_la_ci, (
        "ningún recibo de procedencia cita al job: la deuda "
        "`colector_qg_sin_primera_corrida` vuelve a estar abierta")
