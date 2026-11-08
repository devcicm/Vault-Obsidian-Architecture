"""C‑08 — la capa de despacho del producto entra en el barrido de clones.

`vault_toolkit/` es la frontera instalable del toolkit: `loading.py` decide
cómo se importa un módulo (`import_toolkit_module`, `legacy_scripts_for`).
Hasta el 2026-11-08 el guard de clones —el que exige **un cuerpo, un
dueño** (CN‑05)— no la veía: solo la medía el guard de criterios. La
candidatura C‑08 pedía barrerla, excluyendo la parte generada.

La exclusión no es unaexceptión: `vault_toolkit/operations/` son 97
adaptadores que produce `vault_distribution_sync`, idénticos por
construcción, y medirlos como código es ruido. La parte **escrita a mano**
(`loading.py`, `__init__.py`) sí se mide.

Y las carpetas del barrido no se repiten: las pregunta al dueño del layout
(`vault.kernel.rutas`), que es donde vive el layout.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

import vault_clones as vc  # noqa: E402
from vault.kernel import rutas  # noqa: E402


def _relativos(ficheros) -> set[str]:
    return {str(p.relative_to(REPO_ROOT).as_posix()) for p in ficheros}


def test_el_barrido_mide_la_capa_de_despacho():
    """`loading.py` es código del producto y entra en el barrido."""
    ficheros = _relativos(vc._ficheros(REPO_ROOT))
    assert "vault_toolkit/loading.py" in ficheros, sorted(ficheros)[:5]
    assert "vault_toolkit/__init__.py" in ficheros


def test_el_barrido_excluye_lo_generado():
    """Los 97 adaptadores generados no se miden: son idénticos por
    construcción, así que su presencia no sería una señal sino ruido."""
    ficheros = _relativos(vc._ficheros(REPO_ROOT))
    generados = [f for f in ficheros if f.startswith("vault_toolkit/operations/")]
    assert not generados, generados[:5]
    # Y la carpeta es la que declara el dueño del layout, no un nombre suelto.
    assert set(rutas.GENERADOS) == {"operations"}, rutas.GENERADOS
    assert rutas.GENERADOS["operations"] == rutas.VAULT_TOOLKIT


def test_las_zonas_las_pregunta_el_layout_y_no_se_repiten():
    """Un solo sitio dice qué se barre: el dueño del layout."""
    base = vc._bases(REPO_ROOT, True)
    nombres = {p.name for p in base}
    esperados = set(rutas.CARPETAS_DE_CODIGO_PYTHON)
    assert nombres == esperados, (nombres, esperados)
    # Y el guard de criterios mide lo mismo (por eso el criterio se puede
    # contrastar entre los dos sin pasar por una lista intermedia).
    import vault_criterios as vcri

    assert set(vcri._ZONAS_DE_DEFINICION) == esperados, (
        vcri._ZONAS_DE_DEFINICION, esperados)


def test_entrar_en_el_barrido_no_engorda_la_deuda():
    """La condición que el repo pone: la baseline solo encoge. Con la capa de
    despacho dentro, la deuda medida sigue siendo cero."""
    veredicto = vc.check()
    assert veredicto["ok"] is True, veredicto
    assert veredicto["clone_groups_total"] == 0, veredicto
    assert veredicto["shadowing_total"] == 0, veredicto
    assert veredicto["new_clones"] == [] and veredicto["new_shadowing"] == [], veredicto
    # Y el guard dice qué midió: sin eso, «no hay clones» y «no miré ahí» se
    # leen igual.
    assert "vault_toolkit" in veredicto["zones_scanned"], veredicto
    assert veredicto["generated_excluded"] == ["operations"], veredicto
