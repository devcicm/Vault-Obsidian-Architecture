"""F8 (no repudio) se mide con un criterio que el manifiesto no publica.

El registro (`vault_fundamentals_catalog`, F8) verifica que «al menos una entrada
en .change-log.json referencia la ruta de la nota», y `vault_quality_check` lo
aplica a **toda** nota. El manifiesto, en la tabla de dimensiones, pide «1 por
borrado». Y `vault_write` no anota creaciones en el change-log, así que en un
vault recién poblado toda nota viva puntúa 0 en `non_repudiation`: medido el
2026-10-14 con la wheel instalada, 26 notas de 26.

Cuál de los dos manda es una decisión de producto, no de quien mide, y el usuario
la dejó declarada como deuda (`f8_criterio_sin_decidir`). Este test fijaba el
límite: fallaba el día que el registro y el manifiesto dijeran lo mismo.

Saldada el 2026-10-15 con la opción (a): `vault_write` anota altas y cambios
(`tests/test_f8_vault_write_anota.py`, que la sostiene) y el manifiesto dice
«1 por nota». El límite se conserva invertido —no-derogación—: ahora vigila que
el cierre no se deshaga rebajando el criterio en vez de cumplirlo.
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
    # Invertido al saldarse (2026-10-15): la divergencia quedó cerrada en la
    # dirección del registro, no rebajándolo.
    f8 = next(f for f in FUNDAMENTALS if f["id"] == "F8")
    assert any("referencia la ruta de la nota" in v for v in f8["verifies"])
    fila = next(l for l in (REPO_ROOT / "vault-obsidian-architecture.md").read_text(
        encoding="utf-8").splitlines() if l.startswith("| No repudio (F8)"))
    assert "1 por borrado" not in fila
    # El criterio sigue siendo el del registro: una nota viva sin entrada, 0.
    assert q._score_non_repudiation("07_Knowledge/viva.md", set())[0] == 0.0
