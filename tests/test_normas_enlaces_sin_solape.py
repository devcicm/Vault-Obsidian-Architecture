"""Las normas de enlaces (AP-14, AP-21, AP-22, SP-02) no se pisan.

Medido el 2026-10-07 contra el código, que es quien decide (AP-44):

- `vault_audit._detect_broken_links` no cuenta como roto un `[[carpeta/nota]]`
  que resuelve, y `vault_lib.ruta_necesaria` acepta la ruta que desambigua
  (AP-21 precisado en v40.35). Pero AP-14 seguía diciendo «o links con path
  (AP-21)» y «(b) path-anchored» entre sus causas, y su señal se atribuía el
  `[[]]` (AP-22) y el `[[folder/nota]]` (AP-21): el mismo enlace era correcto
  para una norma y roto para la otra.
- La distinción AP-14 / AP-21 decía que AP-21 «se rompe en cuanto la nota se
  mueve», cuando `vault_move` reescribe los `[[carpeta/nota]]` entrantes.
- AP-14, AP-22 y SP-02 recetaban la misma prevención —buscar antes de linkar—
  y AP-22 no declaraba en qué se distingue de las otras dos.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from vault_norms_catalog import NORM_CATALOG  # noqa: E402


def _n(codigo: str) -> dict:
    return next(n for n in NORM_CATALOG if n["code"] == codigo)


def test_ap14_no_cuenta_como_roto_el_enlace_con_carpeta():
    n = _n("AP-14")
    assert "(AP-21)" not in n["description"]
    assert "path-anchored" not in n["description"]
    assert "[[folder/nota]]" not in n["signal"]
    assert "[[]]" not in n["signal"], "el [[]] vacío lo señala AP-22"


def test_la_distincion_ap14_ap21_no_contradice_a_vault_move():
    for a, b in (("AP-14", "AP-21"), ("AP-21", "AP-14")):
        texto = _n(a)["distinguido_de"][b]
        assert "se rompe en cuanto la nota se mueve" not in texto
        assert "candidat" in texto or "resuelve a" in texto


@pytest.mark.parametrize("otra", ["AP-14", "SP-02"])
def test_ap22_declara_de_que_se_distingue(otra):
    assert (_n("AP-22").get("distinguido_de") or {}).get(otra, "").strip()
    assert (_n(otra).get("distinguido_de") or {}).get("AP-22", "").strip()


@pytest.mark.parametrize("codigo", ["AP-14", "AP-22"])
def test_quien_receta_buscar_antes_de_linkar_cita_a_sp02(codigo):
    """Buscar el destino antes de escribir el enlace es SP-02. Otra norma puede
    remitir a ese protocolo, pero no recetarlo como propio."""
    prev = _n(codigo)["prevention"]
    if "vault_search" in prev or "antes de linkar" in prev or "exista antes" in prev:
        assert "SP-02" in prev, f"{codigo} receta el protocolo de SP-02 sin citarla"


def test_ap22_no_se_atribuye_el_aviso_de_ghost_links():
    """`ghost_links[]` es el aviso de SP-02 por un destino que no existe; un
    `[[]]` no tiene destino. AP-22 puede nombrarlo solo para remitir a SP-02."""
    d = _n("AP-22")["description"]
    if "ghost_links" in d:
        assert "SP-02" in d
