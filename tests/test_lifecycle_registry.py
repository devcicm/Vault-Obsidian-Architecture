"""El catálogo de máquinas de estado, contrastado contra los registros que describe.

`01-state-machines.md` es el documento del SDD cuyo trabajo entero es decir qué
estados tiene cada cosa. Se generaba desde una cadena constante de trece filas
escritas a mano, y **dos estaban mal**: daba el ciclo de la versión del estándar
como «v19 → v20 → … → v36» estando el repo en v39.5, y el de las tools como
`active / deprecated / internal / meta / removed`, dos de cuyos valores el
tool-spec no usa y uno de los que sí usa (`archived`) no aparecía.

Nada lo detectó porque no había con qué contrastar: la prosa era la única
fuente. Ahora la tabla deriva de `vault_norms.LIFECYCLE_REGISTRY` y estas
pruebas son el guard que falla cuando el registro y la fuente viva divergen.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_io  # noqa: E402
import vault_norms as vn  # noqa: E402
import vault_sdd_init as sdd  # noqa: E402
from vault_standard_upgrade import CURRENT_VERSION  # noqa: E402


@pytest.fixture(scope="module")
def doc():
    return sdd.generate_state_machines(REPO_ROOT / "vault-sandbox", {})


def _fila(clave):
    return next(f for f in vn.LIFECYCLE_REGISTRY if f.get("source") == clave)


def test_el_registro_existe_y_no_esta_vacio():
    assert len(vn.LIFECYCLE_REGISTRY) >= 13


def test_cada_lifecycle_nombra_una_tool_que_existe():
    """La tabla decía `tool-spec.json` y `(manual)` donde debería ir una tool.

    Una columna «Tool» que no nombra una tool ejecutable no le sirve a nadie:
    el lector no puede pasar del estado a la acción.
    """
    catalogo = json.loads(
        (REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8")
    )["tools"]
    spec = json.loads(
        Path(vault_io.resolve_tool_spec()).read_text(encoding="utf-8")
    )["tools"]
    for f in vn.LIFECYCLE_REGISTRY:
        assert f["tool"] in catalogo or f["tool"] in spec, f


def test_los_estados_de_tool_salen_del_tool_spec(doc):
    """La fila viva, contrastada contra el fichero, no contra sí misma (AP-44)."""
    spec = json.loads(
        Path(vault_io.resolve_tool_spec()).read_text(encoding="utf-8")
    )["tools"]
    esperado = " / ".join(sorted({e.get("status", "active") for e in spec.values()}))
    assert esperado in doc, esperado
    for inventado in ("meta / removed", "deprecated / internal / meta"):
        assert inventado not in doc


def test_la_version_del_estandar_es_la_actual(doc):
    assert CURRENT_VERSION in doc
    assert "v36 |" not in doc, "la fila de versión volvió a quedarse fija"


def test_las_filas_vivas_no_declaran_estados():
    """Declarar estados y resolverlos a la vez es AP-05: dos fuentes.

    Si alguien rellena `states` en una fila con `source`, la constante gana y el
    documento vuelve a poder quedarse atrás sin que nada falle.
    """
    for clave in ("tool_spec_status", "standard_version"):
        assert _fila(clave)["states"] is None


def test_el_generador_ya_no_es_prosa_constante():
    assert "generate_state_machines" not in sdd.constant_generators()


def test_las_dos_tablas_traen_todas_las_filas(doc):
    """Bilingüe: ES y EN describen lo mismo o el documento miente en un idioma."""
    for f in vn.LIFECYCLE_REGISTRY:
        assert f"**{f['entity']}**" in doc, f["entity"]
        assert f"**{f['entity_en']}**" in doc, f["entity_en"]
