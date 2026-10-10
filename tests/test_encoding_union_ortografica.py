"""AP-44 — sanear el contenido no borra un ZWNJ/ZWJ que es ortografía.

Medido como consumidor el 2026-10-10: `vault_write` con «می» + ZWNJ + «خواهم» (persa) y
«क्» + ZWJ + «ष» (hindi) devolvía `ok: true` y en disco quedaba «میخواهم» y «क्ष»: el
U+200C y el U+200D se borraban siempre por estar en `INVISIBLE_CHARS`. En esas
escrituras —y en las secuencias de emoji (👩 + ZWJ + 💻)— el carácter es parte de la
palabra; quitarlo cambia lo que dice la nota sin avisar.

Entre dos letras latinas, o pegado a un espacio, no une nada: ahí sigue siendo
el invisible que el saneador existe para quitar (`pass` + ZWJ + `word`).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_encoding as ve  # noqa: E402

ZWNJ, ZWJ = "\u200c", "\u200d"


@pytest.mark.parametrize("texto", [
    f"می{ZWNJ}خواهم",               # persa: prefijo verbal separado sin espacio
    f"क्{ZWJ}ष",                     # devanagari: forma media explícita
    f"👩{ZWJ}💻",                    # secuencia de emoji
    f"❤️{ZWJ}🔥",                    # con selector de variante delante
])
def test_la_union_ortografica_se_conserva(texto):
    limpio, fixes = ve.remove_invisible_chars(texto)
    assert limpio == texto
    assert fixes == []
    assert all(i["type"] != "invisible_char" for i in ve.detect_issues(texto))


@pytest.mark.parametrize("texto,esperado", [
    (f"pass{ZWJ}word", "password"),
    (f"pass{ZWNJ}word", "password"),
    (f"{ZWNJ}hola", "hola"),
    (f"hola {ZWJ} mundo", "hola  mundo"),
    (f"می{ZWNJ}", "می"),
])
def test_fuera_de_una_escritura_que_une_se_quita(texto, esperado):
    limpio, fixes = ve.remove_invisible_chars(texto)
    assert limpio == esperado
    assert fixes and fixes[0]["count"] == 1
    assert any(i["type"] == "invisible_char" for i in ve.detect_issues(texto))


def test_sanitize_content_conserva_el_persa_entero():
    texto = f"persa: می{ZWNJ}خواهم y un pass{ZWJ}word"
    limpio, _ = ve.sanitize_content(texto, dry_run=False)
    assert f"می{ZWNJ}خواهم" in limpio
    assert "password" in limpio
