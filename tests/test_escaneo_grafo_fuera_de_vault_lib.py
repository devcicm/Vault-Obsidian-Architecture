"""AP-59: el escaneo del grafo vive en su propio módulo del núcleo.

`vault_kernel` (K3) marcó `vault_lib` como inestable: veinte commits frente a
un escalón de 17,5, y nueve de ellos caían en el escaneo del grafo de
wikilinks, que consumen tres módulos de los setenta que dependen de
`vault_lib`. La reestructuración lo saca a `vault_escaneo_grafo`; la identidad
(`indice_de_nombres`, `resolver_wikilink`, `colisiones_de_nombre`) se queda,
porque de ella deriva `indice_de_destinos`. Estos tests fallan si el bloque
vuelve a `vault_lib` o si el módulo nuevo deja de tener forma de núcleo.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_arch  # noqa: E402
import vault_escaneo_grafo  # noqa: E402
import vault_lib  # noqa: E402

_ESCANEO = ("escanear_wikilinks", "leer_notas_de_grafo", "resolver_enlaces", "_lista_de_cadenas")
_IDENTIDAD = ("indice_de_nombres", "resolver_wikilink", "colisiones_de_nombre", "indice_de_destinos")


def _definidas(modulo) -> set:
    arbol = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
    return {n.name for n in arbol.body if isinstance(n, ast.FunctionDef)}


def test_ap59_el_escaneo_no_vuelve_a_vault_lib():
    assert not set(_ESCANEO) & _definidas(vault_lib)
    assert set(_ESCANEO) <= _definidas(vault_escaneo_grafo)


def test_ap59_la_identidad_se_queda_en_vault_lib():
    assert set(_IDENTIDAD) <= _definidas(vault_lib)
    assert vault_escaneo_grafo.indice_de_nombres is vault_lib.indice_de_nombres


def test_ap59_el_escaneo_es_nucleo_y_solo_importa_nucleo():
    kernel = set(vault_arch.CONTEXTS["kernel"]["modulos"])
    assert "vault_escaneo_grafo" in kernel
    arbol = ast.parse(Path(vault_escaneo_grafo.__file__).read_text(encoding="utf-8"))
    propios = {n.module for n in ast.walk(arbol)
               if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("vault")}
    assert propios and propios <= kernel, propios
