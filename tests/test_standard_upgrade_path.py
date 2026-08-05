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


def test_scripts_dir_esta_definido():
    """Se usaba en dos ramas sin estar definido nunca.

    Ambas estaban dentro de un `except Exception`, así que el NameError no
    rompía: salía como `fixes_failed: "name 'SCRIPTS_DIR' is not defined"` en
    `standard-version.json` y la migración seguía devolviendo `ok: true`.
    """
    assert vsu.SCRIPTS_DIR.is_dir()
    assert (vsu.SCRIPTS_DIR / "vault_standard_upgrade.py").exists()


def test_toda_tool_de_fix_declarada_existe_como_script():
    """El nombre del script es el de la tool, sin derivaciones.

    La versión anterior lo reconstruía como `vault_<segunda palabra>.py`: para
    `vault_fix_brackets` daba `vault_fix.py`, que no existe. El fix nunca se
    aplicaba y el fallo solo quedaba anotado en el registro del vault.
    """
    faltan = []
    for fix_type, config in vsu.FIX_TYPES.items():
        tool = config["tool"]
        if not (vsu.SCRIPTS_DIR / f"{tool}.py").exists():
            faltan.append((fix_type, tool))
    assert not faltan, f"fixes que invocan scripts inexistentes: {faltan}"

    # Y que toda migración referencie un fix_type registrado.
    for version, migracion in vsu.MIGRATIONS.items():
        for fix_type in migracion.get("fixes", []):
            assert fix_type in vsu.FIX_TYPES, f"{version} cita el fix desconocido {fix_type}"


def test_un_fallo_resuelto_no_queda_fijado_en_el_registro():
    """`fixes_applied` / `fixes_failed` se escriben siempre, incluso vacías.

    Con el `if` anterior, una migración sin fallos no sobrescribía la clave, y
    el vault seguía declarando un error ya corregido, versión tras versión.
    """
    fuente = (vsu.SCRIPTS_DIR / "vault_standard_upgrade.py").read_text(encoding="utf-8")
    assert 'state["fixes_failed"] = all_fixes_failed' in fuente
    assert "if all_fixes_failed:" not in fuente
