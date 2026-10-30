"""D-02 — `superseded_by` lo escribe y lo lee el estandar, asi que el contrato lo declara.

Antes se usaba (adaptadores lo lee para excluir lo reemplazado) sin figurar en
`CAMPOS`: un consumidor que validara con el JSON Schema no sabia que existia.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vault.kernel.contrato_nota import CAMPOS, HISTORIA  # noqa: E402


def test_superseded_by_esta_declarado_como_opcional_de_contenido():
    d = CAMPOS["superseded_by"]
    assert d["nivel"] == "opcional" and d["clases"] == ("contenido",)
    assert d["no_vacio"] is True


def test_superseded_by_tiene_fecha_en_la_historia():
    assert any("superseded_by" in c["campos"] for c in HISTORIA["v41"])
