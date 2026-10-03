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


def test_ap46_revocar_una_preferencia_no_convierte_null_en_texto(vault):
    """Revocar volvía a serializar el dict entero a mano: lo que no era texto,
    lista ni dict salía con `str()`, y un campo nulo volvía como "None"."""
    import vault_preferences

    r = vault_preferences.vault_preferences_set(
        "style", HOSTIL, "nunca: usar #tabs", agent="bot")
    assert r["ok"], r
    nota = vault / r["path"]
    bloque, cuerpo = separar_frontmatter(nota.read_text(encoding="utf-8"))
    nota.write_text("---\n" + bloque + "\nrevisado_por: \n---\n" + cuerpo, encoding="utf-8")
    antes = yaml.safe_load(bloque)

    r = vault_preferences.vault_preferences_revoke(r["path"], "a: b #c", agent="bot")
    assert r["ok"], r
    texto = nota.read_text(encoding="utf-8")
    fm = yaml.safe_load(_bloque(texto))
    assert fm["revisado_por"] is None
    assert fm["title"] == HOSTIL and fm["statement"] == antes["statement"]
    assert fm["revoked_reason"] == "a: b #c" and isinstance(fm["revoked_at"], str)
    assert fm["createdAt"] == antes["createdAt"] and fm["preference_state"] == "revoked"
    assert len(_claves(texto)) == len(set(_claves(texto)))


def test_ap46_propagar_marca_una_vez_y_limpiar_no_toca_el_cuerpo(vault):
    """La marca se reemplaza en su sitio y va citada, como siempre. Limpiarla
    con `re.sub` sobre el contenido entero borraba también la línea del
    cuerpo que la documentaba."""
    import vault_propagate

    nota = vault / "07_Knowledge" / "n.md"
    cuerpo = "\nEjemplo:\npropagation_pending: algo\n"
    nota.write_text(f"---\ntitle: '{HOSTIL}'\n---\n" + cuerpo, encoding="utf-8")
    assert vault_propagate._action_notify("07_Knowledge/n.md", "2026-10-02T00:00:00Z")
    assert vault_propagate._action_notify("07_Knowledge/n.md", "2026-10-03T00:00:00Z")
    texto = nota.read_text(encoding="utf-8")
    assert _claves(texto) == ["title", "propagation_pending"]
    assert yaml.safe_load(_bloque(texto))["propagation_pending"] == "2026-10-03T00:00:00Z"

    r = vault_propagate.vault_propagate_clear("07_Knowledge/n.md")
    texto = nota.read_text(encoding="utf-8")
    assert _claves(texto) == ["title"] and texto.endswith(cuerpo)
    assert yaml.safe_load(_bloque(texto))["title"] == HOSTIL

    nota.write_text(f"---\ntitle: t\n---\n" + cuerpo, encoding="utf-8")
    vault_propagate.vault_propagate_clear("07_Knowledge/n.md")
    assert nota.read_text(encoding="utf-8").endswith(cuerpo)


def test_ap46_el_erd_de_relation_add_conserva_el_proyecto(vault):
    import vault_relation_add

    r = vault_relation_add.vault_relation_add(FECHA_PROYECTO, "a", "b", "depends_on")
    assert r["ok"], r
    [erd] = list(vault.rglob("*-erd.md"))
    fm = yaml.safe_load(_bloque(erd.read_text(encoding="utf-8")))
    assert fm["project"] == FECHA_PROYECTO and fm["title"] == f"{FECHA_PROYECTO} ERD"


FECHA_PROYECTO = "2026-10-02"
