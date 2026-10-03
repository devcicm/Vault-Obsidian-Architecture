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


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "07_Knowledge", "17_Preferences"):
        (root / sec).mkdir(parents=True)
    vault_io.set_vault_root(root)
    return root


def test_ap46_aplicar_una_norma_respeta_una_lista_en_bloque(vault):
    """AP-44: `norm_refs:\n- AP-01` es una lista YAML válida. El regex por
    líneas la leía como el valor `- AP-01` y la reescribía `["- AP-01", …]`."""
    import vault_norms

    nota = vault / "07_Knowledge" / "n.md"
    nota.write_text(
        f"---\ntitle: '{HOSTIL}'\nnorm_refs:\n- AP-01\nn: 1\n---\n\ncuerpo\n",
        encoding="utf-8",
    )
    r = vault_norms.vault_norms_apply("AP-05", "07_Knowledge/n.md")
    assert r["ok"], r
    texto = nota.read_text(encoding="utf-8")
    fm = yaml.safe_load(_bloque(texto))
    assert fm["norm_refs"] == ["AP-01", "AP-05"] and fm["title"] == HOSTIL
    assert _claves(texto) == ["title", "norm_refs", "n"]
    assert texto.endswith("\n---\n\ncuerpo\n")
    assert vault_norms.vault_norms_apply("AP-05", "07_Knowledge/n.md")["message"].endswith("present")
