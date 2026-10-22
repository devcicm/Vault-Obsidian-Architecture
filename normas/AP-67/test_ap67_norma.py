"""AP-67 desde su paquete: la entrada que sirve el catálogo es la de aquí.

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


def test_ap67_el_catalogo_sirve_la_entrada_del_paquete():
    import vault_norms_catalog

    assert vault_norms_catalog.norma_por_codigo("AP-67") == _norma()


def test_ap67_la_norma_se_distingue_de_sus_vecinas():
    """Una norma que no dice de qué se distingue no se puede aplicar: el
    criterio se solapa y la tool que la aplica no sabe cuál manda."""
    norma = _norma()
    assert set(norma["distinguido_de"]) >= {"AP-15", "AP-36", "AP-05"}
    for vecina, texto in norma["distinguido_de"].items():
        assert len(texto) > 80, f"{vecina}: la discriminacion no explica nada"


def test_ap67_la_herramienta_que_la_aplica_la_nombra_en_su_cuerpo():
    """La cara derivada se genera de aqui: si la tool deja de nombrar la
    norma, `vault_norms --check-framework` falla."""
    import vault_code_sync

    fuente = Path(vault_code_sync.__file__).read_text(encoding="utf-8")
    assert "AP-67" in fuente, "la tool que aplica AP-67 tiene que nombrarla"
