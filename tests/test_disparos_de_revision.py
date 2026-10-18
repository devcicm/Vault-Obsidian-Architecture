"""R5 — `vault_norms_coherence --disparos`: qué normas toca revisar y por qué.

Dos disparos, los dos decidibles sin interpretar:

- **cadencia**: `revisado_en + cadencia_dias` ya pasó (el registro de R4,
  `vault_norms_catalog.gestion_de_normas`);
- **código**: un fichero de una tool que sostiene la norma —la aplica, la
  detecta, la sigue o la sana— cambió en git después de `revisado_en`. La norma
  puede seguir siendo cierta, pero ya nadie lo ha comprobado contra ese código.

Disparar no es fallar: la salida es una lista de trabajo y la puerta no la mira.
Sin git el segundo disparo no se puede medir y la salida lo dice, en vez de
salir vacía como si no hubiera nada que revisar (AP-60).
"""

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_norms_coherence as coh  # noqa: E402

HOY = date(2026, 10, 15)


def _norma(code, revisado, **extra):
    base = {"code": code, "enforcement": "audit", "revisado_en": revisado,
            "tools_enforcing": [], "tools_detecting": ["vault_audit"]}
    base.update(extra)
    return base


def test_dispara_por_cadencia_vencida():
    r = coh.disparos(hoy=HOY, catalogo=[_norma("AP-99", "2026-01-01")],
                     fecha_de=lambda ruta: "2025-12-01")
    assert [d["code"] for d in r["disparos"]] == ["AP-99"]
    assert r["disparos"][0]["motivos"][0]["disparo"] == "cadencia"


def test_dispara_por_codigo_cambiado_despues_de_la_revision():
    r = coh.disparos(hoy=HOY, catalogo=[_norma("AP-99", "2026-10-01")],
                     fecha_de=lambda ruta: "2026-10-10")
    motivos = r["disparos"][0]["motivos"]
    assert motivos == [{"disparo": "codigo", "tool": "vault_audit",
                        "cambiado_en": "2026-10-10"}]


def test_el_mismo_dia_no_dispara():
    r = coh.disparos(hoy=HOY, catalogo=[_norma("AP-99", "2026-10-10")],
                     fecha_de=lambda ruta: "2026-10-10")
    assert r["disparos"] == []
    assert r["normas_medidas"] == 1


def test_las_tools_de_sanacion_tambien_sostienen_la_norma():
    # AP-56 la sana vault_frontmatter_heal (SANADORES), aunque no la detecte.
    vistos = []
    coh.disparos(hoy=HOY, catalogo=[_norma("AP-56", "2026-10-10", tools_detecting=[])],
                 fecha_de=lambda ruta: vistos.append(Path(ruta).name) or "2026-10-01")
    assert any("frontmatter_heal" in n for n in vistos)


def test_sin_git_lo_dice_en_vez_de_salir_vacio():
    r = coh.disparos(hoy=HOY, catalogo=[_norma("AP-99", "2026-10-01")],
                     fecha_de=lambda ruta: None)
    assert r["codigo_sin_medir"] == ["vault_audit"]
    assert r["disparos"] == []


def test_disparos_sobre_el_catalogo_real():
    # Reloj real: el catálogo real envejece con él, no con HOY (r53).
    r = coh.disparos(hoy=date.today())
    assert r["ok"] is True
    import vault_norms_catalog as cat
    assert r["normas_medidas"] == len(cat.NORM_CATALOG)
    for d in r["disparos"]:
        assert d["motivos"] and all(m["disparo"] in ("cadencia", "codigo") for m in d["motivos"])
