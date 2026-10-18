"""R4 — gestión de normas: quién responde de cada una, cuándo se revisó y cada
cuánto toca volver a mirarla.

Una norma con guard que nadie revisa envejece igual que una sin él: el guard
sigue en verde midiendo lo que la norma decía hace un año. El registro vive en
el catálogo (`vault_norms_catalog.gestion_de_normas`), `revisado_en` en cada
`norma.py` —es un hecho por norma— y `responsable` y `cadencia_dias` se derivan
salvo que el paquete los declare, para no copiar la misma constante en cada
paquete (AP-47). `vault_norms --check-framework` falla si el registro está mal
formado; una norma vencida sale en `alertas` y en la métrica `normas_vencidas`,
no rompe la puerta: vencer es trabajo pendiente, no una contradicción.
"""

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_norms_catalog as cat  # noqa: E402


def test_toda_norma_tiene_responsable_revision_y_cadencia():
    # El catálogo real se mide contra el reloj real: con una fecha fija, la
    # primera revisión posterior a ella salía «en el futuro» (r53, AP-40).
    g = cat.gestion_de_normas(hoy=date.today())
    assert g["problemas"] == []
    assert len(g["normas"]) == len(cat.NORM_CATALOG)
    for n in g["normas"]:
        assert n["responsable"]
        assert isinstance(n["cadencia_dias"], int) and n["cadencia_dias"] > 0
        date.fromisoformat(n["revisado_en"])


def test_la_cadencia_se_deriva_del_enforcement():
    assert cat.CADENCIA_POR_ENFORCEMENT == {
        "guard": 90, "audit": 90, "guard+audit": 90, "recommended": 180}
    assert cat.RESPONSABLE_POR_DEFECTO == "mantenedor"
    for n in cat.gestion_de_normas(hoy=date(2026, 10, 15))["normas"]:
        norma = cat.norma_por_codigo(n["code"])
        if "cadencia_dias" not in norma:
            assert n["cadencia_dias"] == cat.CADENCIA_POR_ENFORCEMENT[norma["enforcement"]]


def test_una_norma_vencida_sale_como_vencida_y_no_como_problema():
    norma = {"code": "AP-99", "enforcement": "audit", "revisado_en": "2026-01-01"}
    g = cat.gestion_de_normas(hoy=date(2026, 10, 15), catalogo=[norma])
    assert g["problemas"] == []
    assert [v["code"] for v in g["vencidas"]] == ["AP-99"]
    assert g["vencidas"][0]["vence_en"] == "2026-04-01"


def test_el_registro_mal_formado_es_un_problema():
    malas = [
        {"code": "AP-97", "enforcement": "audit"},                          # sin revisado_en
        {"code": "AP-98", "enforcement": "audit", "revisado_en": "ayer"},   # fecha ilegible
        {"code": "AP-99", "enforcement": "audit", "revisado_en": "2027-01-01"},  # futura
        {"code": "AP-96", "enforcement": "manual", "revisado_en": "2026-10-01"},  # sin cadencia
    ]
    g = cat.gestion_de_normas(hoy=date(2026, 10, 15), catalogo=malas)
    assert sorted(p["code"] for p in g["problemas"]) == ["AP-96", "AP-97", "AP-98", "AP-99"]


def test_check_framework_publica_la_gestion_y_falla_si_esta_mal():
    import vault_norms_engine as eng

    r = eng.framework_drift_check()
    assert "gestion_de_normas" in r
    assert r["gestion_de_normas"]["problemas"] == []
    assert "vencidas" in r["gestion_de_normas"]


def test_la_metrica_normas_vencidas_esta_registrada():
    import vault_metricas as vm

    m = next(m for m in vm.METRICAS if m["id"] == "normas_vencidas")
    assert m["origen"] == "calculada" and m["sentido"] == "menor"
    assert vm.problemas_de_registro(m) == []
    assert vm.CALCULOS["normas_vencidas"]() == len(
        cat.gestion_de_normas()["vencidas"])
