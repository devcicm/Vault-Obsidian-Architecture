"""`vault_tags --rename` a un tag acentuado no revienta.

La línea nueva se pasaba a `re.sub` como plantilla, y `json.dumps` escribe
`configuración` como `configuraci\\u00f3n`: `re` lee `\\u` como escape de
plantilla y lanza `bad escape \\u`. Un tag en español —el idioma del
estándar— no se podía renombrar. Con `\\1` en el nombre, la plantilla
insertaba el grupo capturado en vez del texto.
"""

import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_io  # noqa: E402
import vault_tags  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    original = vault_io.get_vault_root()
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\ntype: knowledge\ntags: [\"config\", \"api\"]\n---\n\n"
        "Cuerpo con contenido suficiente.\n",
        encoding="utf-8",
    )
    vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(original)


@pytest.mark.parametrize("nuevo", ["configuración", "ruta\\1"])
def test_renombrar_a_un_tag_con_escapes_de_plantilla(vault, nuevo):
    r = vault_tags.vault_tags_rename("config", nuevo)
    assert r["ok"] is True, r
    assert r["updated_count"] == 1
    texto = (vault / "07_Knowledge" / "nota.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(texto.split("---")[1])
    assert fm["tags"] == [nuevo, "api"]


def test_ap46_renombrar_con_tags_en_lista_de_bloque(vault):
    """Auditoría del 2026-10-15: el `re.sub` cambiaba solo la línea `tags:`.

    Con `tags:` en bloque (`- a` debajo), dejaba los ítems viejos colgando del
    valor nuevo; el guard de `atomic_write` lo frenaba con
    `FRONTMATTER_PARSE_ERROR`, pero las notas anteriores ya estaban renombradas
    y el registro no se reconstruía: un renombrado a medias. Ahora reescribe el
    campo el dueño, `Frontmatter.editar`, que reemplaza la clave con su
    continuación.
    """
    (vault / "07_Knowledge" / "bloque.md").write_text(
        "---\ntitle: Bloque\ntype: knowledge\ntags:\n  - config\n  - otro\n---\n\n"
        "Cuerpo con contenido suficiente.\n",
        encoding="utf-8",
    )
    r = vault_tags.vault_tags_rename("config", "ajustes")
    assert r["ok"] is True, r
    assert r["updated_count"] == 2, r
    for nombre, resto in (("nota.md", "api"), ("bloque.md", "otro")):
        texto = (vault / "07_Knowledge" / nombre).read_text(encoding="utf-8")
        fm = yaml.safe_load(texto.split("---")[1])
        assert fm["tags"] == ["ajustes", resto], (nombre, texto)
