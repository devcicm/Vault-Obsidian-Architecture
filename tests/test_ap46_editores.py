"""AP-46: los editores reescriben el frontmatter por su dueño.

Cada editor tenía su forma de tocar un bloque que ya existía —añadir líneas al
final, `re.sub` por clave, volver a serializar el dict con `json.dumps` o
`str()`— y cada forma tenía su fallo. Ahora pasan por `Frontmatter.editar`, y
el criterio de estos tests es el del consumidor (AP-44): `yaml.safe_load` y,
donde importa, que ninguna clave aparezca dos veces.
"""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402

HOSTIL = 'Ñandú "x": v2 #y'


def _bloque(texto: str) -> str:
    bloque, _ = separar_frontmatter(texto)
    assert bloque is not None, texto[:300]
    return bloque


def _claves(texto: str) -> list:
    return [l.split(":")[0] for l in _bloque(texto).split("\n")
            if l and l[:1] not in (" ", "-")]


def test_ap46_fusionar_dos_veces_no_duplica_mergedFrom():
    from vault_merge import _tag_frontmatter

    nota = "---\ntitle: t\n---\n\ncuerpo\n"
    una = _tag_frontmatter(nota, "a.md")
    dos = _tag_frontmatter(una, HOSTIL)
    assert _claves(dos).count("mergedFrom") == 1
    fm = yaml.safe_load(_bloque(dos))
    assert fm["mergedFrom"] == HOSTIL and fm["title"] == "t"
    assert dos.endswith("\n---\n\ncuerpo\n")
    sin_bloque = _tag_frontmatter("solo cuerpo\n", "a.md")
    assert sin_bloque.endswith("\n---\n\nsolo cuerpo\n")
