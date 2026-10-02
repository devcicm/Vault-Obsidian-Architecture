"""AP-17: el nombre de una nota es su ID, y dos nombres distintos no comparten clave.

La clave con la que un wikilink resuelve a un fichero quitaba los puntos y
después un `md` final, así que `cmd.md` y `c.md` —dos notas— tenían la misma
clave: una sombra canónica fabricada por el propio normalizador. El dueño es
`vault.kernel.normalizacion.clave_de_nombre`; `vault_io.normalize_stem` y el
respaldo de `vault_lib` delegan o coinciden con él.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from vault.kernel.normalizacion import clave_de_nombre  # noqa: E402

DISTINTOS = [("cmd", "c"), ("cmd.md", "c.md"), ("rmd", "r"), ("Café", "Cafe2"), ("a/b", "ab")]
IGUALES = [
    ("Mi Proyecto Demo", "mi-proyecto-demo.md"),
    ("mi_proyecto_demo", "Mi Proyecto Demo"),
    ("Índice", "indice.md"),
    ("NOTA.MD", "nota"),
    ("v1.2", "v12"),
]


@pytest.mark.parametrize("a,b", DISTINTOS)
def test_ap17_nombres_distintos_no_comparten_id(a, b):
    assert clave_de_nombre(a) != clave_de_nombre(b)


@pytest.mark.parametrize("a,b", IGUALES)
def test_ap17_el_mismo_nombre_escrito_distinto_es_el_mismo_id(a, b):
    assert clave_de_nombre(a) == clave_de_nombre(b)


@pytest.mark.parametrize("a,b", DISTINTOS + IGUALES)
def test_ap17_vault_io_usa_la_misma_clave(a, b):
    import vault_io

    for x in (a, b):
        assert vault_io.normalize_stem(x) == clave_de_nombre(x), x


def test_ap17_el_respaldo_de_vault_lib_coincide_con_el_nucleo():
    import re
    import unicodedata

    fuente = (REPO / "scripts" / "vault_lib.py").read_text(encoding="utf-8")
    defs = [n for n in ast.parse(fuente).body
            if isinstance(n, ast.FunctionDef) and n.name in ("fold_accents", "clave_de_nombre")]
    assert len(defs) == 2
    ns = {"re": re, "unicodedata": unicodedata, "Any": object}
    exec(compile(ast.Module(body=defs, type_ignores=[]), "respaldo", "exec"), ns)
    for a, b in DISTINTOS + IGUALES:
        for x in (a, b):
            assert ns["clave_de_nombre"](x) == clave_de_nombre(x), x
