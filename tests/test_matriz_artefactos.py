"""AP-05: la matriz de trazabilidad no inventa dónde vive un artefacto.

La fila de Consistencia (F2) señalaba `00_System/graph.json`; el grafo vive en
`99_Index/` desde que existe, y nadie lo vio porque la matriz es prosa con
forma de registro. Una ruta de artefacto del vault tiene un dueño
—`cli.registry.GUARDED_ARTIFACTS`, verificado contra el vault real— y la
matriz lo consulta en vez de escribir la suya.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from cli.registry import GUARDED_ARTIFACTS  # noqa: E402
from vault_fundamentals import TRACEABILITY_MATRIX  # noqa: E402

_RUTA_DE_VAULT = re.compile(r"^\d\d_[A-Za-z_]+/[^/]+\.\w+$")


def test_ap05_toda_ruta_de_artefacto_de_la_matriz_es_una_ruta_registrada():
    rutas = [f["artifact"] for f in TRACEABILITY_MATRIX if _RUTA_DE_VAULT.match(f["artifact"])]
    assert rutas, "el patrón dejó de reconocer las rutas de la matriz"
    ajenas = sorted(set(rutas) - GUARDED_ARTIFACTS)
    assert ajenas == [], ajenas
