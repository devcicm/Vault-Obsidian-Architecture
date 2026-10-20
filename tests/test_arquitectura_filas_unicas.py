"""AP-47: el plano derivado no repite una frontera por cada línea de import.

`cruces()` publica un sitio por import —es la medida `crossings_sites`— y el
plano pintaba una fila por sitio: `vault_subgraph → vault/grafo` salía tres
veces, y el título «Fronteras que hoy cruza (5)» contaba sitios donde decía
fronteras. Una cifra que no mide lo que nombra es la que AP-47 existe para
impedir, aunque la haya escrito un generador.
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_arch as arch  # noqa: E402
import pytest

pytestmark = pytest.mark.slow  # carril rápido (-m "not slow"): el perfil de la suite del 2026-10-20 midió aquí llamadas > 25 s



def _filas_de_fronteras(texto):
    return [l for l in texto.splitlines()
            if l.startswith("| `") and l.count("|") == 4]


def test_ap47_una_fila_por_frontera_en_el_plano():
    filas = _filas_de_fronteras(arch.blueprint())
    repetidas = [f for f, n in Counter(filas).items() if n > 1]
    assert repetidas == [], repetidas


def test_ap47_el_titulo_cuenta_fronteras_y_no_sitios():
    texto = arch.blueprint()
    pares = {(c["from"], c["to"]) for c in arch.cruces()}
    filas = _filas_de_fronteras(texto)
    assert len(filas) == len(pares)
    if len(pares) < len(arch.cruces()):
        assert "imports)" in texto, "los sitios repetidos dejaron de verse"
