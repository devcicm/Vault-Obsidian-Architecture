"""Dónde acaba el frontmatter lo decide un solo sitio, y por líneas (AP-57).

Medido en la comparativa v34/v40 (2026-10-01): `vault_validate` daba por rota
una nota válida cuyo título llevaba `---` entre comillas, y catorce módulos más
partían igual, con `split("---", 2)`. Obsidian y `yaml.safe_load` —el criterio
del consumidor (AP-44)— cierran el bloque en una **línea** `---`, no en
cualquier `---` del texto.
"""

from vault.kernel.frontmatter_parsing import (
    parse_frontmatter,
    parse_frontmatter_with_body,
    separar_frontmatter,
)

NOTA = (
    '---\n'
    'title: "Antes --- después"\n'
    'status: draft\n'
    '---\n'
    '\n'
    '# Cuerpo\n'
    'texto con --- en medio\n'
)


def test_un_guion_triple_dentro_de_un_valor_no_cierra_el_bloque():
    bloque, cuerpo = separar_frontmatter(NOTA)
    assert bloque == 'title: "Antes --- después"\nstatus: draft'
    assert cuerpo == '\n# Cuerpo\ntexto con --- en medio\n'
    assert parse_frontmatter(NOTA)["title"] == "Antes --- después"


def test_una_linea_que_empieza_por_guiones_no_es_el_cierre():
    # `---más` a columna 0 no es un marcador de documento para YAML —le falta
    # el espacio—, es una clave. El regex viejo cerraba ahí y perdía `---más`.
    texto = "---\nk: v\n---más: x\n---\ncuerpo\n"
    bloque, cuerpo = separar_frontmatter(texto)
    assert cuerpo == "cuerpo\n"
    assert parse_frontmatter(texto) == {"k": "v", "---más": "x"}
    assert parse_frontmatter_with_body(texto)[1] == "cuerpo\n"


def test_reensamblar_devuelve_los_mismos_bytes():
    """Quien reescribe el bloque no puede comerse la línea en blanco del cuerpo."""
    bloque, cuerpo = separar_frontmatter(NOTA)
    assert "---\n" + bloque + "\n---\n" + cuerpo == NOTA


def test_sin_bloque_o_sin_cierre_no_hay_frontmatter():
    assert separar_frontmatter("# solo cuerpo\n") == (None, "# solo cuerpo\n")
    sin_cierre = "---\ntitle: x\n\ncuerpo sin cierre\n"
    assert separar_frontmatter(sin_cierre) == (None, sin_cierre)


def test_bloque_vacio_crlf_y_bom():
    assert separar_frontmatter("---\n---\ncuerpo") == ("", "cuerpo")
    assert separar_frontmatter("---\r\nk: v\r\n---\r\ncuerpo") == ("k: v", "cuerpo")
    assert separar_frontmatter("﻿---\nk: v\n---\ncuerpo") == ("k: v", "cuerpo")
    assert separar_frontmatter("---\nk: v\n---") == ("k: v", "")


def test_el_cuerpo_del_parser_no_cambia():
    """`parse_frontmatter_with_body` sigue entregando el cuerpo sin el blanco inicial."""
    fm, cuerpo = parse_frontmatter_with_body(NOTA)
    assert fm == {"title": "Antes --- después", "status": "draft"}
    assert cuerpo == "# Cuerpo\ntexto con --- en medio\n"
