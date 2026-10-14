"""`run_product_gates` dejaba sus resultados en una carpeta que el vault no declara (CN-02).

El ejecutor guardaba los JSON de cada puerta en `vault-sandbox/product-gates/`,
en la raíz del único vault de pruebas, y `vault_norms --audit` sobre ese mismo
vault salía con un CN-02 de severidad alta que no causaba ninguna nota: lo
causaba el arnés del propio repo. Un sandbox que no cumple las normas por culpa
de quien lo usa para medirlas no distingue un fallo del estándar de uno suyo.

Los informes de un vault viven en `00_System/` (`quality-index.json`, el
`change-log`…), que es sección canónica; la carpeta del ejecutor va ahí.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

import run_product_gates  # noqa: E402
from vault_registry import NON_SECTION_ROOT_FOLDERS, es_de_seccion  # noqa: E402


def test_cn02_los_resultados_del_ejecutor_viven_en_una_carpeta_que_el_vault_declara():
    sandbox = REPO_ROOT / "vault-sandbox"
    rel = run_product_gates.SANDBOX.relative_to(sandbox).as_posix()
    raiz = rel.split("/")[0]
    assert es_de_seccion(f"{rel}/x.md") or raiz in NON_SECTION_ROOT_FOLDERS, rel
