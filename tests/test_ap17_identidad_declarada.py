"""AP-17 por identidad declarada: dos notas que responden al mismo nombre.

La deuda `ap17_compara_solo_la_forma_del_titulo` pedía ir más allá de la forma
del título sin comparar contenido, que el servicio descarta sin embeddings. La
reformulación decidible —como la de AP-05 en v40.15— es comparar la identidad
que la nota **declara**:

- `alias`: un `aliases:` de una coincide con el nombre de fichero o con un alias
  de la otra. Es el criterio de resolución de Obsidian (AP-44): `[[ese nombre]]`
  ya no sabe a cuál de las dos lleva, aunque los títulos no se parezcan.
- `files`: las dos declaran el mismo conjunto no vacío de `files:`. Dos notas
  que documentan exactamente el mismo código compiten por ser la canónica.

Regla 7 (2026-10-09, copias de nueve vaults ajenos, solo lectura): 0 pares por
`alias` y 0 por `files` — sin ruido. La cifra fechada vive en la entrada de la
deuda en `vault_blueprint`, no aquí.
"""

import pytest

import vault_audit
import vault_io


def _nota(vault, rel, fm):
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm}\n---\n\n# Nota\n\nCuerpo.\n", encoding="utf-8")
    return p


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "00_System").mkdir(parents=True)
    vault_io.set_vault_root(v)
    return v


def test_un_alias_que_es_el_nombre_de_otra_nota_es_sombra(vault):
    a = _nota(vault, "07_Knowledge/facturacion.md", "title: Servicio de facturación")
    b = _nota(vault, "01_Projects/billing.md",
              "title: Módulo de cobros\naliases: [facturacion]")
    pares = vault_audit._detect_canonical_shadow([a, b])
    assert [(p["noteA"], p["noteB"], p["motivo"]) for p in pares] == [
        ("07_Knowledge/facturacion.md", "01_Projects/billing.md", "alias")]


def test_dos_notas_con_el_mismo_alias_son_sombra(vault):
    a = _nota(vault, "07_Knowledge/uno.md", "title: Uno\naliases: [Gateway]")
    b = _nota(vault, "07_Knowledge/dos.md", "title: Dos\naliases: [gateway]")
    assert [p["motivo"] for p in vault_audit._detect_canonical_shadow([a, b])] == ["alias"]


def test_el_mismo_conjunto_de_files_es_sombra_y_uno_distinto_no(vault):
    a = _nota(vault, "07_Knowledge/uno.md", "title: Uno\nfiles: [src/a.py, src/b.py]")
    b = _nota(vault, "01_Projects/dos.md", "title: Dos\nfiles: [src/b.py, ./src/a.py]")
    c = _nota(vault, "01_Projects/tres.md", "title: Tres\nfiles: [src/a.py]")
    pares = vault_audit._detect_canonical_shadow([a, b, c])
    assert [(p["noteA"], p["noteB"], p["motivo"]) for p in pares] == [
        ("07_Knowledge/uno.md", "01_Projects/dos.md", "files")]


def test_el_titulo_sigue_siendo_el_primer_motivo(vault):
    a = _nota(vault, "07_Knowledge/a.md", "title: Servicio de facturacion\naliases: [b]")
    b = _nota(vault, "07_Knowledge/b.md", "title: Servicio de facturacion v2")
    assert [p["motivo"] for p in vault_audit._detect_canonical_shadow([a, b])] == ["titulo"]


def test_el_title_no_es_identidad(vault):
    """Un `title:` igual al alias de otra no la hace sombra: Obsidian no lo mira."""
    a = _nota(vault, "07_Knowledge/a.md", "title: Gateway")
    b = _nota(vault, "07_Knowledge/b.md", "title: Otra cosa\naliases: [Pasarela]")
    assert vault_audit._detect_canonical_shadow([a, b]) == []


def test_la_sombra_por_identidad_anotada_con_superseded_by_sale_resuelta(vault):
    a = _nota(vault, "07_Knowledge/facturacion.md", "title: Servicio de facturación")
    b = _nota(vault, "01_Projects/billing.md",
              'title: Módulo de cobros\naliases: [facturacion]\n'
              'superseded_by: "[[07_Knowledge/facturacion]]"')
    resueltos = []
    assert vault_audit._detect_canonical_shadow([a, b], resueltos=resueltos) == []
    assert resueltos and resueltos[0]["canonica"] == "07_Knowledge/facturacion.md"


def test_la_identidad_se_publica_sin_peso_y_el_titulo_sigue_pesando():
    pares = [{"noteA": "a", "noteB": "b", "motivo": "titulo"},
             {"noteA": "c", "noteB": "d", "motivo": "alias"},
             {"noteA": "e", "noteB": "f", "motivo": "files"}]
    pesan, informativos = vault_audit._separar_por_peso(pares)
    assert [p["motivo"] for p in pesan] == ["titulo"]
    assert [p["motivo"] for p in informativos] == ["alias", "files"]
