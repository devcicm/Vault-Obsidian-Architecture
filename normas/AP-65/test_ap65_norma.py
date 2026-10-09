"""AP-65 desde su paquete: la entrada que sirve el catálogo es la de aquí.

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


def test_ap65_el_catalogo_sirve_la_entrada_del_paquete():
    import vault_norms_catalog

    assert vault_norms_catalog.norma_por_codigo("AP-65") == _norma()


def test_ap65_el_criterio_tiene_un_solo_dueno():
    from vault.kernel.contenido import falta_de_evaluacion_de_impacto

    exigidos = ("critical", "high")
    nota = "16_AI_Governance/decisiones/d.md"
    assert falta_de_evaluacion_de_impacto(nota, {"impact_level": "high"}, exigidos)
    assert not falta_de_evaluacion_de_impacto(
        nota, {"impact_level": "high", "impact_assessment": "completa"}, exigidos)
    assert not falta_de_evaluacion_de_impacto(nota, {"impact_level": "low"}, exigidos)


def test_ap65_lo_detecta_quien_el_catalogo_dice():
    for tool in _norma()["tools_detecting"]:
        assert (RAIZ / "scripts" / f"{tool}.py").is_file()
