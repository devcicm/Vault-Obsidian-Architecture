"""AP-08 en prosa espera a que exista el campo que la haría decidible (deuda #2).

La versión escrita en el cuerpo de una nota solo se puede comparar sin adivinar
si la nota la declara en `version_pinned:` —lo que pide la `prevention`— y el
repo tiene un manifiesto con ese paquete. Medido el 2026-10-09: ninguna nota de
las copias de ocho consumidores lo declara, y ninguna tool del estándar lo
escribe. Un detector sobre ese universo vacío saldría verde sin medir (AP-60).
Si una tool empieza a emitirlo, el segundo test lo dirá y la parte en prosa
deja de tener excusa.

Lo dijo en v41.4, que es para lo que estaba: el campo entró en el contrato,
`vault_write --version-pinned` lo emite y `vault_drift_detect --mode vigencia`
lo compara (`test_ap08_version_pinned.py`). El cable trampa se invierte en vez
de borrarse: ahora vigila que quien nombra el campo sea el contrato, su
escritor y su detector, y que el detector no se vaya dejando al escritor solo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vault_norms_catalog import NORM_CATALOG  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def _ap08() -> dict:
    return next(n for n in NORM_CATALOG if n["code"] == "AP-08")


def test_ap08_declara_el_universo_vacio_de_la_parte_en_prosa():
    parcial = _ap08()["cobertura_parcial"]
    assert "version_pinned" in parcial and "2026-10-09" in parcial
    assert "AP-60" in parcial


def test_quien_nombra_version_pinned_es_el_contrato_su_escritor_y_su_detector():
    nombran = {
        p.name for p in (ROOT / "scripts").glob("*.py")
        # Los dos registros lo nombran como dato (la norma y su deuda), no lo emiten.
        if p.name not in {"vault_norms_catalog.py", "vault_blueprint.py"}
        and "version_pinned" in gi.codigo_de(p).read_text(encoding="utf-8")
    }
    # El contrato lo declara, su migración lo anuncia, el escritor lo emite y
    # el detector de AP-08 lo compara. Una tool nueva que lo nombre tiene que
    # entrar aquí a sabiendas; un escritor sin detector vuelve al universo
    # que nadie mide.
    assert nombran == {"vault_contrato_nota.py", "vault_standard_upgrade.py",
                       "vault_write.py", "vault_drift_detect.py"}, sorted(nombran)
