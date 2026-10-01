"""El producto no arrastra a la gobernanza del estándar (grupo 35).

Medido en v40.34: `vault/kernel/adaptadores.NormasDelCatalogo` leía
`NORM_CATALOG` entrando por la fachada `vault_norms`, que importa el motor y,
con él, `vault_smoke`, `vault_voice` y el resto del meta-toolkit. Era la arista
que hacía imposible sacar el grupo 35 de la wheel sin romper `vault`: el dato
vive en la hoja `vault_norms_catalog` desde v40.27 (AP-62).
"""

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _en_proceso_limpio(codigo: str) -> dict:
    salida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout
    return json.loads(salida.strip().splitlines()[-1])


def test_ap62_las_normas_del_producto_salen_de_la_hoja():
    r = _en_proceso_limpio(
        "import json, sys\n"
        "from vault.kernel.adaptadores import NormasDelCatalogo\n"
        "n = NormasDelCatalogo()\n"
        "v = n.vigentes(); c = n.por_codigo(v[0]['code']) is not None\n"
        "print(json.dumps({'vigentes': len(v), 'por_codigo': c, 'cargados': sorted("
        "m for m in sys.modules if m.split('.')[-1] in "
        "('vault_norms', 'vault_norms_engine', 'vault_smoke', 'vault_voice'))}))\n"
    )
    assert r["vigentes"] > 0 and r["por_codigo"]
    assert r["cargados"] == [], f"el producto cargó la gobernanza: {r['cargados']}"


def test_la_hoja_y_la_fachada_dan_el_mismo_catalogo():
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        import vault_norms
        import vault_norms_catalog
    finally:
        sys.path.remove(str(RAIZ / "scripts"))
    assert vault_norms.NORM_CATALOG is vault_norms_catalog.NORM_CATALOG
