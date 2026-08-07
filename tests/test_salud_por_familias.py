"""`healthScore` satura; `healthIndex` no. Y el viejo no cambia ni un punto.

`healthScore` parte de 100 y resta 22 penalizaciones independientes cuyos topes
suman **285**. Basta estar mal en dos o tres familias distintas para llegar a 0,
y a partir de ahí deja de medir: un vault regular y uno perdido puntúan igual.
No es una hipótesis — `vault-sandbox/`, el vault de referencia de este repo y
recién reconstruido, puntúa 0.

La corrección obvia sería recalibrarlo. No se hace, y el motivo no es técnico:
lo leen los repos consumidores, y cambiar por debajo lo que significa un número
publicado es peor que el número malo. Se aplica la política de no-derogación a
una métrica — `healthScore` se queda como está, se anota `superseded_by:
healthIndex`, y lo nuevo va al lado.

El riesgo del refactor era el contrario: mover 22 penalizaciones a un registro
y cambiar el número sin querer. `test_el_refactor_no_movio_ni_un_punto` lo cierra
reimplementando **literalmente** el bloque viejo y comparando.
"""

import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_audit  # noqa: E402


def _score_del_bloque_viejo(u):
    """El cálculo tal y como estaba escrito antes del registro, línea a línea.

    Copiado a propósito: es un control, no una segunda fuente de verdad. Si
    diverge del registro, el que está mal es el registro — y este test lo dice.
    """
    score = 100
    score -= min(30, u["orphans"] * 2)
    score -= min(10, u["stale"] * 1)
    score -= min(15, u["stuck_patterns"] * 3)
    score -= min(25, u["stale_projects"] * 5)
    score -= min(20, u["broken_links"] * 2)
    score -= min(10, u["canonical_shadow"] * 2)
    score -= min(10, u["cross_folder_dupes"] * 3)
    score -= min(5, u["ap22"] * 2)
    score -= min(15, u["ap24"] * 5)
    score -= min(10, u["empty_indexes"] * 2)
    score -= min(20, u["mermaid_errors"] * 2)
    score -= min(10, u["missing_agent"] * 1)
    score -= min(15, u["missing_tags"] * 2)
    score -= min(10, u["missing_type"] * 2)
    score -= min(10, u["missing_status"] * 1)
    score -= min(15, u["missing_cia"] * 2)
    score -= min(10, u["missing_updated"] * 2)
    score -= min(20, u["missing_frontmatter"] * 3)
    score -= min(15, u["cia_penalty"])
    score -= u["ap31"]
    score -= min(10, u["ap34"] * 2)
    if u["ap35"]:
        score -= 5
    return max(0, score)


IDS = [p["id"] for p in vault_audit.PENALIZACIONES]


def test_el_refactor_no_movio_ni_un_punto():
    """500 combinaciones al azar contra el bloque original."""
    rnd = random.Random(20260807)
    for _ in range(500):
        # ap31 llega ya en puntos desde su detector, no en ocurrencias.
        unidades = {i: rnd.randint(0, 12) for i in IDS}
        unidades["ap31"] = rnd.choice([0, 5, 10, 20])
        unidades["ap35"] = rnd.choice([0, 1])
        assert vault_audit.calcular_salud(unidades)["healthScore"] == \
            _score_del_bloque_viejo(unidades), unidades


def test_un_vault_limpio_sigue_puntuando_cien():
    r = vault_audit.calcular_salud({})
    assert r["healthScore"] == 100
    assert r["healthIndex"] == 100
    assert r["penalties"] == []


# ── La saturación, que es el defecto entero ────────────────────────────────

def test_el_score_viejo_no_distingue_donde_el_indice_si():
    """El caso que motiva todo: dos vaults muy distintos, mismo 0.

    Uno tiene un problema serio de conectividad y nada más; el otro lo tiene
    todo roto. `healthScore` dice lo mismo de los dos. Si algún día dejara de
    decirlo, este test hay que reescribirlo — no borrarlo.
    """
    regular = {"orphans": 15, "broken_links": 10, "ap24": 3, "missing_frontmatter": 7,
               "missing_cia": 8, "stale_projects": 5}
    perdido = {i: 99 for i in IDS}
    perdido["ap31"] = 20

    a = vault_audit.calcular_salud(regular)
    b = vault_audit.calcular_salud(perdido)

    assert a["healthScore"] == b["healthScore"] == 0, (
        "si el score dejó de saturar, esta prueba y su motivo cambian"
    )
    assert a["healthIndex"] > b["healthIndex"], (
        "healthIndex tiene que distinguir justo donde healthScore se queda plano"
    )
    assert b["healthIndex"] == 0, "todo al tope sí debe ser 0"


def test_el_indice_solo_llega_a_cero_con_todas_las_familias_al_tope():
    una_familia = {p["id"]: 999 for p in vault_audit.PENALIZACIONES
                   if p["familia"] == "metadatos"}
    r = vault_audit.calcular_salud(una_familia)
    assert r["healthScore"] == 0, "105 puntos de metadatos ya saturan el viejo"
    assert r["healthIndex"] > 0, (
        "una sola familia al tope no puede dejar el índice en 0: es exactamente "
        "la información que healthScore destruye"
    )


def test_el_perfil_dice_que_familia_toco_fondo():
    r = vault_audit.calcular_salud({p["id"]: 999 for p in vault_audit.PENALIZACIONES
                                    if p["familia"] == "grafo"})
    perfil = r["healthProfile"]
    assert perfil["grafo"]["saturated"] is True
    assert perfil["grafo"]["health"] == 0
    assert all(not v["saturated"] for k, v in perfil.items() if k != "grafo")


def test_el_indice_no_lo_decide_una_sola_familia():
    """Media simple y no ponderada por tope, a propósito.

    `metadatos` acumula 105 puntos de tope frente a los 5 de `ap35`. Ponderar
    por tope sería reintroducir el defecto con otro nombre.
    """
    solo_metadatos = vault_audit.calcular_salud(
        {p["id"]: 999 for p in vault_audit.PENALIZACIONES if p["familia"] == "metadatos"}
    )
    solo_grafo = vault_audit.calcular_salud(
        {p["id"]: 999 for p in vault_audit.PENALIZACIONES if p["familia"] == "grafo"}
    )
    assert solo_metadatos["healthIndex"] == solo_grafo["healthIndex"], (
        "una familia al tope debe pesar lo mismo sea cual sea su tope"
    )


# ── El registro ────────────────────────────────────────────────────────────

def test_toda_penalizacion_tiene_una_familia_que_existe():
    for p in vault_audit.PENALIZACIONES:
        assert p["familia"] in vault_audit.FAMILIAS_DE_SALUD, p["id"]


def test_ninguna_familia_se_queda_sin_penalizaciones():
    """Una familia vacía puntuaría 100 por vacía, no por sana."""
    usadas = {p["familia"] for p in vault_audit.PENALIZACIONES}
    assert usadas == set(vault_audit.FAMILIAS_DE_SALUD)


def test_los_topes_por_familia_se_derivan_y_no_se_escriben():
    topes = vault_audit._tope_por_familia()
    for familia, tope in topes.items():
        esperado = sum(p["tope"] for p in vault_audit.PENALIZACIONES
                       if p["familia"] == familia)
        assert tope == esperado


def test_los_topes_suman_mas_de_cien_y_por_eso_satura():
    """La cifra que explica el defecto, medida y no escrita a mano (AP-47)."""
    total = sum(p["tope"] for p in vault_audit.PENALIZACIONES)
    assert total > 100, (
        "si los topes ya no superan 100, healthScore dejó de saturar y toda "
        "esta parte del razonamiento hay que rehacerla"
    )


def test_los_ids_del_registro_son_unicos():
    assert len(IDS) == len(set(IDS))


def test_ninguna_penalizacion_puede_superar_su_tope():
    for p in vault_audit.PENALIZACIONES:
        r = vault_audit.calcular_salud({p["id"]: 10 ** 6})
        aplicada = next(d for d in r["penalties"] if d["id"] == p["id"])
        assert aplicada["penalty"] == p["tope"]


# ── El envelope: lo viejo sigue, lo nuevo acompaña ─────────────────────────

def test_el_envelope_conserva_health_score_y_añade_lo_nuevo():
    """No-derogación aplicada a una métrica: nada desaparece del contrato."""
    r = vault_audit.vault_audit()
    for clave in ("healthScore", "healthIndex", "healthProfile", "penalties"):
        assert clave in r, clave
    assert isinstance(r["healthScore"], int)
    assert 0 <= r["healthIndex"] <= 100


def test_el_sandbox_sigue_siendo_el_ejemplo_del_defecto():
    """Documentado y medido: el vault de referencia del repo puntúa 0.

    Si algún día el sandbox deja de estar en 0, es una buena noticia y este
    test hay que actualizarlo con la cifra nueva — no relajarlo.
    """
    r = vault_audit.vault_audit()
    assert r["healthScore"] == 0
    assert r["healthIndex"] > 0, (
        "el índice tiene que decir algo útil precisamente donde el score no dice nada"
    )


@pytest.mark.parametrize("familia,descripcion", vault_audit.FAMILIAS_DE_SALUD.items())
def test_cada_familia_explica_que_significa(familia, descripcion):
    """El perfil lo lee un humano o un agente: una clave sin glosa no sirve."""
    assert descripcion and len(descripcion) > 10
    r = vault_audit.calcular_salud({})
    assert r["healthProfile"][familia]["means"] == descripcion
