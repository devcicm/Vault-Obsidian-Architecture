"""AP-32 desde su paquete: la entrada que sirve el catálogo es la de aquí.

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


def test_ap32_el_catalogo_sirve_la_entrada_del_paquete():
    import vault_norms_catalog

    assert vault_norms_catalog.norma_por_codigo("AP-32") == _norma()


def test_ap32_las_tools_que_declara_existen():
    import vault_grafo_import

    norma = _norma()
    for campo in ("tools_enforcing", "tools_detecting", "tools_del_patron"):
        for tool in norma.get(campo, []):
            # «vault_x (guard …)» o «vault_io.atomic_write_text»: el módulo es
            # el primer token hasta el punto.
            modulo = tool.split()[0].split(".")[0]
            assert vault_grafo_import.fuente_de(modulo).is_file(), tool
