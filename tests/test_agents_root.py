"""Las tools que aceptan `--root` son las que AGENTS.md nombra en la regla 1.

La regla 1 lleva la cuenta de qué tools aceptan `--root`, y ya se equivocó
dos veces: «solo 4» cuando había un quinto, y el bloque de comandos siguió
diciendo «las cuatro tools de la regla 1» después de que la regla pasara a
nombrar dos conjuntos y seis tools. Una cifra escrita a mano en prosa es
AP-47; aquí la lista sale del argparse de cada tool y se compara con lo que
la regla nombra.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS = REPO_ROOT / "AGENTS.md"

_CIFRAS = {"una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}

import vault_grafo_import as gi  # noqa: E402


def _tools_con_root():
    tools = set()
    for script in (REPO_ROOT / "scripts").glob("*.py"):
        arbol = ast.parse(gi.codigo_de(script).read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"
                    and any(isinstance(a, ast.Constant) and a.value == "--root" for a in nodo.args)):
                tools.add(script.stem)
    return tools


def _regla_1():
    texto = AGENTS.read_text(encoding="utf-8")
    inicio = texto.index("1. **`vault-sandbox/` para cualquier ejecución.**")
    return texto[inicio:texto.index("\n2. **", inicio)]


def test_la_regla_1_nombra_exactamente_las_tools_que_aceptan_root():
    nombradas = set(re.findall(r"`(vault_[a-z_]+)`", _regla_1())) - {"vault_io"}
    assert nombradas == _tools_con_root()


def test_ninguna_cifra_de_tools_de_la_regla_1_contradice_al_argparse():
    """Quien cite «las N tools de la regla 1» tiene que acertar N, o no citarla."""
    total = len(_tools_con_root())
    texto = AGENTS.read_text(encoding="utf-8")
    for m in re.finditer(r"\b(\w+)\s+tools(?:\s|#)+de la regla 1", texto, re.IGNORECASE):
        palabra = m.group(1).lower()
        if palabra in _CIFRAS:
            assert _CIFRAS[palabra] == total, m.group(0)
