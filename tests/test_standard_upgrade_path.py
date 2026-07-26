"""Camino de migración del estándar.

Ancla dos fallos reales encontrados al cerrar v39:

1. `_version_index` solo aceptaba coincidencia exacta contra `VERSION_ORDER`
   (que usa versión mayor, "v39"), mientras `CURRENT_VERSION` trae minor
   ("v39.0"). El índice salía -1 y `_pending_migrations` devolvía [] en
   silencio: `--to latest` no aplicaba NINGUNA migración.
2. `17_Preferences/` existía en el registro pero no en `MIGRATIONS`, así que
   un vault preexistente nunca recibía la carpeta que `vault_preferences`
   necesita como destino.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_registry  # noqa: E402
import vault_standard_upgrade as vsu  # noqa: E402


def test_current_version_resuelve_indice():
    """CURRENT_VERSION debe ser localizable aunque traiga minor."""
    assert vsu._version_index(vsu.CURRENT_VERSION) >= 0


@pytest.mark.parametrize(
    "version,esperado",
    [("v39", "v39"), ("v39.0", "v39"), ("v34.2", "v34"), ("v99.0", None)],
)
def test_version_index_normaliza_minor(version, esperado):
    idx = vsu._version_index(version)
    if esperado is None:
        assert idx == -1
    else:
        assert vsu.VERSION_ORDER[idx] == esperado


def test_latest_aplica_todas_las_migraciones():
    """El bug silencioso: la lista no puede quedar vacía desde la base."""
    pending = vsu._pending_migrations("v20", vsu.CURRENT_VERSION)
    assert pending, "sin migraciones pendientes desde v20: camino roto"
    assert pending[-1] == vsu.VERSION_ORDER[-1]


def test_version_order_contiguo_y_sin_huecos():
    """Un hueco en VERSION_ORDER corta el camino a partir de ese punto.

    v19/v20 son versiones base (punto de partida de `--init`), no tienen
    migración propia: el recorrido arranca en la primera que sí la tiene.
    """
    inicio = vsu.VERSION_ORDER.index("v21")
    for v in vsu.VERSION_ORDER[inicio:]:
        assert v in vsu.MIGRATIONS, f"{v} en VERSION_ORDER pero sin migración"


def test_migracion_v39_crea_17_preferences():
    carpetas = vsu.MIGRATIONS["v39"]["add_folders"]
    assert "17_Preferences" in carpetas
    for sub in ("workflow", "style", "tooling", "constraints", "domain"):
        assert f"17_Preferences/{sub}" in carpetas


def test_toda_seccion_del_registro_es_alcanzable_por_migracion():
    """Registro y migraciones no pueden divergir: si una sección existe en el
    registro pero ninguna migración la crea, los vaults preexistentes se
    quedan sin ella para siempre."""
    creadas = {
        f.split("/")[0]
        for m in vsu.MIGRATIONS.values()
        for f in m.get("add_folders", [])
    }
    base = set(vsu.STANDARD_FOLDERS)
    for seccion in vault_registry.standard_folders():
        assert seccion in base or seccion in creadas, (
            f"{seccion} está en el registro pero ninguna migración ni el "
            f"scaffold base la crea"
        )
