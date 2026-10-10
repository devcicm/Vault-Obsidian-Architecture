"""Las caras `guard.py` y `heal.py` de cada paquete de norma (deuda #10).

El paquete tenía `norma.py`, `porque.md` y su test; las caras que aplican y
reparan la norma vivían en la prosa de `porque.md` o en ninguna parte. Ahora
son ficheros de datos **derivados**: cada `ruta::símbolo` es una función que
nombra la norma en su cuerpo dentro de una tool que el catálogo declara, y
`heal.py` sale del registro `vault_norms_catalog.SANADORES`, que es por tool y
no por norma. Apuntan al dueño; no copian su criterio.
"""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _ruta in (ROOT / "scripts", ROOT):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import vault_norms_catalog as cat  # noqa: E402
import vault_norms_engine as engine  # noqa: E402

NORMAS = ROOT / "normas"


def _datos(fichero: Path) -> dict:
    """Las asignaciones de un `guard.py`/`heal.py`, sin ejecutarlo."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"))
    out = {}
    for n in arbol.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            out[n.targets[0].id] = ast.literal_eval(n.value)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out[n.target.id] = ast.literal_eval(n.value)
    return out


def test_todo_paquete_tiene_sus_cinco_caras():
    problemas = cat.forma_de_paquetes()
    assert problemas == []
    for carpeta in sorted(p for p in NORMAS.iterdir()
                          if p.is_dir() and not p.name.startswith(("_", "."))):
        assert (carpeta / "guard.py").is_file(), carpeta.name
        assert (carpeta / "heal.py").is_file(), carpeta.name


def test_las_caras_en_disco_son_las_derivadas():
    assert engine.caras_desfasadas() == []


def test_ap22_y_ap24_las_repara_fix_brackets():
    assert cat.tools_healing("AP-22") == ["vault_fix_brackets"]
    heal = _datos(NORMAS / "AP-22" / "heal.py")["HEAL"]
    assert heal and all(c.startswith("scripts/vault_fix_brackets.py::") for c in heal)
    assert "vault_fix_brackets" in cat.tools_healing("AP-24")


def test_ap14_la_repara_graph_fix_en_la_funcion_que_reescribe_el_enlace():
    heal = _datos(NORMAS / "AP-14" / "heal.py")["HEAL"]
    assert "vault/grafo/graph_fix.py::_process_note" in heal
    heal21 = _datos(NORMAS / "AP-21" / "heal.py")["HEAL"]
    assert "vault/grafo/graph_fix.py::_fix_path_anchored" in heal21


def test_ap65_no_tiene_heal_y_lo_dice():
    """Saber a quién afecta una decisión no lo escribe un programa por nadie."""
    datos = _datos(NORMAS / "AP-65" / "heal.py")
    assert datos["HEAL"] is None
    assert "AP-65" in datos["MOTIVO"]
    assert cat.tools_healing("AP-65") == []


def test_guard_apunta_a_la_funcion_del_dueno():
    guard = _datos(NORMAS / "AP-65" / "guard.py")["GUARD"]
    assert "scripts/vault_norms.py::vault_norms_scan" in guard


def test_un_sanador_que_no_nombra_la_norma_falla_la_forma(monkeypatch):
    """El registro afirmaría un heal que nadie puede seguir hasta el código (AP-55)."""
    monkeypatch.setitem(cat.SANADORES, "vault_supersede", ("AP-17", "AP-65"))
    derivadas = engine.caras_derivadas("AP-65", ROOT)
    assert any("vault_supersede" in p for p in derivadas["problemas"])


def test_una_cara_editada_a_mano_se_detecta(tmp_path):
    copia = tmp_path / "normas"
    shutil.copytree(NORMAS / "AP-22", copia / "AP-22",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (copia / "AP-22" / "heal.py").write_text("HEAL = None\nMOTIVO = 'a mano'\n",
                                             encoding="utf-8")
    problemas = engine.caras_desfasadas(raiz=copia, raiz_repo=ROOT)
    assert [p["paquete"] for p in problemas] == ["AP-22"]
    assert "heal.py" in problemas[0]["problema"]


def test_check_framework_publica_las_caras_desfasadas():
    r = engine.framework_drift_check()
    assert r["paquetes_de_norma"]["caras_desfasadas"] == []
