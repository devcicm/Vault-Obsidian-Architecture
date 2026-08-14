"""Los seis parsers de frontmatter que había, contra el dueño canónico (AP-44).

Hasta v40.23 seis módulos —`vault_code_query`, `vault_list`, `vault_pattern_save`,
`vault_project_overview`, `vault_read`, `vault_runbook_log`— parseaban el
frontmatter con un regex línea a línea. Medido sobre el corpus de
`vault-sandbox/` antes de migrar, ese regex devolvía `{}` en **110 de 126**
notas: `^---\\n` no casa `---\\r\\n` y no sobrevive al BOM de Windows, y el
corpus real tiene las dos cosas. Devolver `{}` no es un error visible: es la
respuesta legítima de «esta nota no tiene frontmatter», así que la ceguera
llevaba versiones sin que ninguna puerta la viera.

Estos tests fijan las dos mitades de la migración: que los seis dan hoy
exactamente lo que da el dueño, y que el dueño ve lo que el regex no veía.
"""

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from vault_lib import parse_frontmatter  # noqa: E402

MODULOS = [
    "vault_code_query",
    "vault_list",
    "vault_pattern_save",
    "vault_project_overview",
    "vault_runbook_log",
]

#: El parser que había, tal cual estaba escrito en los seis módulos. Se conserva
#: aquí —y solo aquí— para poder medir la diferencia; no lo llama ninguna tool.
def _regex_de_antes(content: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    return meta


def _corpus():
    notas = sorted((RAIZ / "vault-sandbox").rglob("*.md"))
    assert notas, "sin corpus no hay contraste que valga"
    return notas


@pytest.mark.parametrize("modulo", MODULOS)
def test_los_cinco_dan_lo_mismo_que_el_dueno_sobre_el_corpus(modulo):
    mod = __import__(modulo)
    for nota in _corpus():
        texto = nota.read_text(encoding="utf-8", errors="replace")
        assert mod.parse_frontmatter(texto) == parse_frontmatter(texto), nota


def test_vault_read_delega_y_conserva_su_propio_contrato_de_cuerpo():
    """Devuelve `(meta, body)` y el cuerpo va sin espacios en los bordes.

    Ese `.strip()` es de esta tool, no del dueño: `parse_frontmatter_with_body`
    devuelve el cuerpo tal cual. Se mantiene para no cambiar la salida de
    `vault_read` al migrar el parseo.
    """
    import vault_read

    for nota in _corpus():
        texto = nota.read_text(encoding="utf-8", errors="replace")
        meta, cuerpo = vault_read.parse_frontmatter(texto)
        esperado_meta = parse_frontmatter(texto)
        assert meta == esperado_meta, nota
        assert cuerpo == cuerpo.strip()


def test_el_regex_de_antes_era_ciego_al_bom_y_al_crlf():
    """La razón de la migración, fijada como dato y no como afirmación."""
    nota = "﻿---\r\ntitle: Demo\r\nevergreen: true\r\n---\r\ncuerpo\r\n"
    assert _regex_de_antes(nota) == {}
    assert parse_frontmatter(nota) == {"title": "Demo", "evergreen": True}


def test_el_regex_de_antes_leia_todo_valor_como_texto():
    """`'false'` es una cadena verdadera: el tipo perdido cambia decisiones."""
    nota = "---\nevergreen: false\ncount: 3\ntags: [a, b]\n---\ncuerpo\n"
    antes = _regex_de_antes(nota)
    assert antes["evergreen"] == "false" and bool(antes["evergreen"]) is True
    ahora = parse_frontmatter(nota)
    assert ahora["evergreen"] is False
    assert ahora["count"] == 3
    assert ahora["tags"] == ["a", "b"]


def test_ninguno_de_los_seis_conserva_el_regex_de_frontmatter():
    """Que la copia no vuelva: seis cuerpos iguales es como empezó esto (AP-57)."""
    for modulo in MODULOS + ["vault_read"]:
        fuente = (RAIZ / "scripts" / f"{modulo}.py").read_text(encoding="utf-8")
        assert r'r"^---\n(.*?)\n---"' not in fuente, modulo
