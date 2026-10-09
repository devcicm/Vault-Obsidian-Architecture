"""AP-04 sigue descubierta, y su última hipótesis está medida (deuda #2).

La intención —planeada frente a inventada— es lo que separa AP-04 de AP-01.
Se probó si quedaba escrita en la historia del `status`: una nota entregada que
en git tuvo antes un estado planificado. Medido el 2026-10-09 contra la copia
de /ans, la señal fue nula. Estos tests fijan que la norma no se da por
cubierta sin detector y que el motivo medido no desaparece del catálogo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vault_norms_catalog import NORM_CATALOG  # noqa: E402


def _ap04() -> dict:
    return next(n for n in NORM_CATALOG if n["code"] == "AP-04")


def test_ap04_no_tiene_detector_y_lo_declara():
    norma = _ap04()
    assert norma["tools_detecting"] == []
    assert "cobertura_descubierta" in norma
    assert "cobertura_parcial" not in norma


def test_ap04_conserva_la_hipotesis_de_la_historia_medida():
    motivo = _ap04()["cobertura_descubierta"]
    assert "historia" in motivo and "2026-10-09" in motivo
    assert "nula" in motivo
