"""AP-08 en prosa espera a que exista el campo que la haría decidible (deuda #2).

La versión escrita en el cuerpo de una nota solo se puede comparar sin adivinar
si la nota la declara en `version_pinned:` —lo que pide la `prevention`— y el
repo tiene un manifiesto con ese paquete. Medido el 2026-10-09: ninguna nota de
las copias de ocho consumidores lo declara, y ninguna tool del estándar lo
escribe. Un detector sobre ese universo vacío saldría verde sin medir (AP-60).
Si una tool empieza a emitirlo, el segundo test lo dirá y la parte en prosa
deja de tener excusa.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vault_norms_catalog import NORM_CATALOG  # noqa: E402


def _ap08() -> dict:
    return next(n for n in NORM_CATALOG if n["code"] == "AP-08")


def test_ap08_declara_el_universo_vacio_de_la_parte_en_prosa():
    parcial = _ap08()["cobertura_parcial"]
    assert "version_pinned" in parcial and "2026-10-09" in parcial
    assert "AP-60" in parcial


def test_ninguna_tool_del_estandar_escribe_version_pinned():
    escritores = [
        p.name for p in (ROOT / "scripts").glob("*.py")
        # Los dos registros lo nombran como dato (la norma y su deuda), no lo emiten.
        if p.name not in {"vault_norms_catalog.py", "vault_blueprint.py"}
        and "version_pinned" in p.read_text(encoding="utf-8")
    ]
    assert escritores == [], (
        "una tool ya emite version_pinned: la parte en prosa de AP-08 es "
        f"decidible y su detector se debe escribir ({escritores})")
