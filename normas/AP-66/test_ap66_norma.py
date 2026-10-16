"""AP-66 desde su paquete: la entrada que sirve el catálogo es la de aquí.

Sin fixtures: lo ejecuta `tests/test_normas_paquete.py`, que es lo que corren
la CI y el `Makefile`, y también `pytest normas/`.
"""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
for _ruta in (RAIZ / "scripts", RAIZ):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))


def _norma():
    arbol = ast.parse((Path(__file__).parent / "norma.py").read_text(encoding="utf-8"))
    return next(ast.literal_eval(n.value) for n in arbol.body
                if isinstance(n, ast.Assign) and n.targets[0].id == "NORMA")


def test_ap66_el_catalogo_sirve_la_entrada_del_paquete():
    import vault_norms_catalog

    assert vault_norms_catalog.norma_por_codigo("AP-66") == _norma()


def test_ap66_el_criterio_marca_la_forma_y_no_su_vecina():
    import vault_arch

    cuadratico = ast.parse(
        "def f(a):\n    for n in ast.walk(a):\n        ast.walk(a)\n")
    lineal = ast.parse(
        "def f(a):\n    for n in ast.walk(a):\n        ast.walk(n)\n")
    assert [h["kind"] for h in vault_arch.costes_que_crecen_en(cuadratico)] == [
        "recorrido_dentro_de_su_recorrido"]
    assert vault_arch.costes_que_crecen_en(lineal) == []
