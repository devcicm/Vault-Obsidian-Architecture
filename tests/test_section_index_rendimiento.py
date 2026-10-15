"""AP-47 sin coste cuadrático: el índice de sección no recorre el vault por render.

Medido el 2026-10-14 con cProfile en una copia de /ans (3498 ficheros):
`vault_frontmatter_completar --apply` tardó 2990 s en escribir 504 notas, y el
75 % se iba en `inventario_de_nombres`, llamado 2210 veces. Cada escritura
regenera el índice de su sección y el de cada subcarpeta, y cada render
volvía a inventariar el vault entero para elegir el destino de los wikilinks.
El inventario no cambia entre los renders de una misma regeneración.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_section_index as vsi  # noqa: E402

NOTA = "---\ntitle: {t}\ntype: note\nstatus: active\n---\n\nCuerpo de {t}.\n"


@pytest.fixture
def vault(tmp_path):
    previo = vault_io.get_vault_root()
    for rel in ("01_Projects/demo/overview.md", "01_Projects/billing/overview.md",
                "01_Projects/billing/plan.md", "01_Projects/raiz.md"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(NOTA.format(t=p.stem), encoding="utf-8")
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previo)


def _contando(monkeypatch):
    llamadas = []
    original = vsi.inventario_de_nombres

    def contado(*a, **kw):
        llamadas.append(1)
        return original(*a, **kw)

    monkeypatch.setattr(vsi, "inventario_de_nombres", contado)
    return llamadas


def test_ap47_una_regeneracion_inventaria_el_vault_una_sola_vez(vault, monkeypatch):
    llamadas = _contando(monkeypatch)
    r = vsi.vault_section_index("01_Projects")
    assert r["ok"], r
    # Sección + dos subcarpetas: tres renders, un inventario.
    assert len(r["subdirIndexes"]) == 2
    assert len(llamadas) == 1



def test_ap47_el_inventario_compartido_elige_el_mismo_destino(vault):
    # Las dos `overview` exigen ruta (AP-21): si el inventario compartido
    # perdiera notas, el índice de la sección enlazaría por nombre ambiguo.
    vsi.vault_section_index("01_Projects")
    texto = (vault / "01_Projects/index.md").read_text(encoding="utf-8")
    assert "[[demo/overview" in texto and "[[billing/overview" in texto
