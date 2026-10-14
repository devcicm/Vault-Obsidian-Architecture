"""F8 (no repudio) se mide con un criterio que el manifiesto no publica.

El registro (`vault_fundamentals_catalog`, F8) verifica que «al menos una entrada
en .change-log.json referencia la ruta de la nota», y `vault_quality_check` lo
aplica a **toda** nota. El manifiesto, en la tabla de dimensiones, pide «1 por
borrado». Y `vault_write` no anota creaciones en el change-log, así que en un
vault recién poblado toda nota viva puntúa 0 en `non_repudiation`: medido el
2026-10-14 con la wheel instalada, 26 notas de 26.

Cuál de los dos manda es una decisión de producto, no de quien mide, y el usuario
la dejó declarada como deuda (`f8_criterio_sin_decidir`). Este test fija el
límite: falla el día que el registro y el manifiesto digan lo mismo, y entonces
la deuda pasa a `saldada` con el test que la sostenga.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_blueprint as bp  # noqa: E402
import vault_quality_check as q  # noqa: E402
from vault_fundamentals_catalog import FUNDAMENTALS  # noqa: E402


def test_la_deuda_de_f8_esta_declarada():
    d = next((d for d in bp.DEUDA_DECLARADA if d["id"] == "f8_criterio_sin_decidir"), None)
    assert d is not None
    assert d["estado"] == "pendiente" or d.get("sostenida_por")


def test_limite_declarado_f8_registro_y_manifiesto_divergen():
    f8 = next(f for f in FUNDAMENTALS if f["id"] == "F8")
    assert any("referencia la ruta de la nota" in v for v in f8["verifies"])
    fila = next(l for l in (REPO_ROOT / "vault-obsidian-architecture.md").read_text(
        encoding="utf-8").splitlines() if l.startswith("| No repudio (F8)"))
    assert "1 por borrado" in fila
    # La medida aplica el criterio del registro a una nota viva sin entrada.
    assert q._score_non_repudiation("07_Knowledge/viva.md", set())[0] == 0.0
