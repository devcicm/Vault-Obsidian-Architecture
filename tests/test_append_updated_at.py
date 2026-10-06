"""`vault_append` refresca `updatedAt`: un append es una escritura (AP-13).

Medido el 2026-10-05: `vault_append` añadía contenido y dejaba `updatedAt` en
la fecha de creación. F6 (actualidad) y `vault_context_pack` leen ese campo,
así que una nota recién ampliada se auditaba como obsoleta y se ordenaba como
vieja. Solo se refresca si la nota ya lo declara: append es no destructivo y
no le cambia el esquema a una nota ajena; que falte es cosa de F3.
"""

import yaml

import vault_append
from vault_lib import separar_frontmatter

VIEJO = "2020-01-01T00:00:00.000Z"


def _vault(tmp_path, monkeypatch, texto):
    (tmp_path / "00_System").mkdir()
    nota = tmp_path / "nota.md"
    nota.write_bytes(texto.encode("utf-8"))
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setattr(vault_append, "get_vault_root", lambda: tmp_path)
    return nota


def _fm(nota):
    bloque, cuerpo = separar_frontmatter(nota.read_bytes().decode("utf-8"))
    return yaml.safe_load(bloque), cuerpo


def test_ap13_append_refresca_updated_at(tmp_path, monkeypatch):
    nota = _vault(tmp_path, monkeypatch,
                  f"---\nid: n\ncreatedAt: {VIEJO}\nupdatedAt: {VIEJO}\ntags: [a]\n---\n\n# N\n\ncuerpo\n")
    r = vault_append.vault_append("nota.md", "linea", timestamped=False)
    assert r["ok"]
    fm, cuerpo = _fm(nota)
    nuevo = str(fm["updatedAt"])
    assert not nuevo.startswith("2020"), nuevo
    assert r["updatedAt"] and r["updatedAt"][:19] == nuevo.replace(" ", "T")[:19]
    # Lo demás no se toca: createdAt, el orden de claves y el cuerpo.
    assert str(fm["createdAt"]).startswith("2020")
    assert list(fm) == ["id", "createdAt", "updatedAt", "tags"]
    assert cuerpo == "\n# N\n\ncuerpo\n\nlinea\n"


def test_ap13_en_seccion_tambien(tmp_path, monkeypatch):
    nota = _vault(tmp_path, monkeypatch,
                  f"---\nupdatedAt: {VIEJO}\n---\n\n# N\n\n## A\n\nuno\n\n## B\n\ndos\n")
    assert vault_append.vault_append("nota.md", "x", section="A", timestamped=False)["ok"]
    fm, cuerpo = _fm(nota)
    assert not str(fm["updatedAt"]).startswith("2020")
    assert cuerpo == "\n# N\n\n## A\n\nuno\n\nx\n\n## B\n\ndos\n"


def test_sin_updated_at_no_se_anade(tmp_path, monkeypatch):
    texto = "---\nid: n\n---\n\n# N\n\ncuerpo\n"
    nota = _vault(tmp_path, monkeypatch, texto)
    r = vault_append.vault_append("nota.md", "linea", timestamped=False)
    assert r["ok"] and r["updatedAt"] is None
    assert nota.read_bytes().decode("utf-8") == texto + "\nlinea\n"


def test_sin_frontmatter_no_se_crea(tmp_path, monkeypatch):
    nota = _vault(tmp_path, monkeypatch, "cuerpo\n")
    r = vault_append.vault_append("nota.md", "linea", timestamped=False)
    assert r["ok"] and r["updatedAt"] is None
    assert nota.read_bytes().decode("utf-8") == "cuerpo\n\nlinea\n"


# ── «¿Declara la clave?» lo contesta el mismo que la reemplaza (AP-57) ────────


def test_el_editor_dice_si_declara_una_clave():
    from vault.kernel.frontmatter_escritura import Frontmatter
    fm = Frontmatter.editar("id: n\nupdatedAt: x\ntags:\n- a\n")
    assert fm.tiene("updatedAt") and fm.tiene("tags")
    assert not fm.tiene("updated") and not fm.tiene("createdAt")


def test_append_no_decide_por_su_cuenta_si_la_clave_existe():
    r"""Hasta v40.36 `vault_append` lo miraba con `^updatedAt\s*:` y `set`
    reemplaza lo que encuentra `_tramo` con `^clave\s*:(\s|$)`: dos criterios
    para la misma pregunta, y donde discrepan `set` añadiría una segunda línea."""
    import ast
    from pathlib import Path
    fuente = Path(vault_append.__file__).read_text(encoding="utf-8")
    patrones = [n.value for n in ast.walk(ast.parse(fuente))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and "updatedAt" in n.value and r"\s" in n.value]
    assert patrones == []
