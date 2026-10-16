"""AP-66 — el coste crece con lo que no es trabajo.

Auditoría del 2026-10-15: las puertas tardaban 132 s y cinco sitios crecían
con algo distinto de lo que medían. `vault_baseline.pendiente` lanzaba un
`git show` por cada línea que había devuelto otro proceso —un proceso por
commit de la historia—, y `vault_grafo_import._en_funcion` recorría el árbol
entero dentro de su propio recorrido. Se arreglaron uno a uno (0238503,
8e9d639, c44cbea, e9a2f04); este test vigila que las dos formas que se pueden
reconocer sin ejecutar no vuelvan a entrar.
"""

import ast
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_arch  # noqa: E402


def _tipos(codigo: str) -> list[str]:
    arbol = ast.parse(textwrap.dedent(codigo))
    return [h["kind"] for h in vault_arch.costes_que_crecen_en(arbol)]


def test_ap66_un_proceso_por_linea_de_otro_proceso_se_marca():
    # La forma de `pendiente` antes de 0238503.
    assert _tipos("""
        def pendiente():
            salida = vault_subproceso.ejecutar(["git", "log"])
            for commit in salida.stdout.splitlines():
                vault_subproceso.ejecutar(["git", "show", commit])
    """) == ["proceso_por_linea_de_proceso"]
    assert _tipos("""
        def f():
            out = subprocess.check_output(["git", "rev-list", "HEAD"])
            return [subprocess.run(["git", "show", c]) for c in out.split()]
    """) == ["proceso_por_linea_de_proceso"]


def test_ap66_un_recorrido_dentro_de_su_propio_recorrido_se_marca():
    assert _tipos("""
        def f(arbol):
            for nodo in ast.walk(arbol):
                for otro in ast.walk(arbol):
                    pass
    """) == ["recorrido_dentro_de_su_recorrido"]


def test_ap66_lo_que_crece_con_el_trabajo_no_se_marca():
    # Recorrer el subárbol de cada nodo es lineal en lo que se mide.
    assert _tipos("""
        def f(arbol):
            for nodo in ast.walk(arbol):
                for hijo in ast.walk(nodo):
                    pass
    """) == []
    # Un proceso por objetivo declarado es el trabajo, no un sobrecoste.
    assert _tipos("""
        def f(objetivos):
            for t in objetivos:
                subprocess.run(["pytest", t])
    """) == []
    # Un proceso que lee la salida de otro sin bucle tampoco.
    assert _tipos("""
        def f():
            r = subprocess.run(["git", "log"])
            subprocess.run(["git", "show", r.stdout])
    """) == []


def test_ap66_el_repo_no_tiene_costes_que_crecen():
    assert vault_arch.costes_que_crecen() == []
    r = vault_arch.check()
    assert r["growing_costs"] == []
