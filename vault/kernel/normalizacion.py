"""Normalización de cadenas: dueño único de los tres niveles de un texto.

Un mismo título se mira de tres formas, y mezclarlas fue el defecto de G-4
(v40.34): la ruta se decidía con un slug agresivo y el conflicto con igualdad
exacta, así que ``"MI  TITLE"`` sobre ``"Mi Title"`` —el mismo título para
cualquier lector— salía como conflicto, mientras que ``"C++"`` y ``"C#"``
compartían ``c.md`` y solo los separaba la casualidad del ``==``.

1. **Clave de ruta** (``slugify`` / ``slugify_strict``): el nombre de fichero.
   Translitera acentos y quita puntuación; pierde información a propósito.
2. **Clave de equivalencia** (``clave_de_equivalencia``): decide si dos valores
   son *el mismo* dato. NFKC + ``casefold`` + espacios colapsados. Conserva
   acentos y símbolos: ``"Café"`` y ``"Cafe"`` son títulos distintos, y
   ``"C++"`` y ``"C#"`` también.
3. **Valor de presentación**: el texto tal como lo escribió el usuario. No
   tiene función porque no se transforma; se guarda sin tocar.

Hoja del núcleo: solo ``re`` y ``unicodedata``. ``scripts/vault_lib`` reexporta
el slug desde aquí; ``tests/test_slug_canonico.py`` falla si otro módulo —en
``scripts/``, ``cli/`` o ``vault/``— vuelve a implementar el suyo (AP-57).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

__all__ = [
    "fold_accents", "plegar_diacriticos_latinos", "slugify", "slugify_strict",
    "clave_de_equivalencia", "equivalentes", "clave_de_nombre",
]

#: Letras que NFKD no descompone en base + marca y que borrar las destrozaría.
_TRANSLITERACION_EXPLICITA = {
    "ß": "ss", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
}


def fold_accents(text: str) -> str:
    """Translitera acentos a su base ASCII (``"Índice"`` → ``"Indice"``).

    No es cosmético: el que borra los acentos en vez de transliterarlos produce
    nombres ilegibles (``'Características'`` → ``'caracter-sticas'``) y
    wikilinks que heredan el destrozo. Salió al correr el onboarding contra un
    proyecto real en español (regla 7 de AGENTS.md, corolario de AP-44).
    """
    text = "".join(_TRANSLITERACION_EXPLICITA.get(ch, ch) for ch in text)
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def plegar_diacriticos_latinos(texto: str) -> str:
    """Quita diacríticos solo cuando la base es latina; el resto queda intacto.

    ``fold_accents`` borra toda marca combinante, y fuera del alfabeto latino
    eso cambia la palabra: ``"ブログ"`` pierde el dakuten y pasa a ``"フロク"``,
    ``"й"`` pasa a ``"и"``. Aquí ``"migración"`` → ``"migracion"`` y
    ``"Straße"`` → ``"Strasse"``, pero ``"ブログ"`` y ``"Проект"`` salen tal cual
    (en NFC). La clave de ruta no usa esta función para no mover ficheros ya
    escritos; la usan las claves nuevas, como la etiqueta.
    """
    texto = "".join(_TRANSLITERACION_EXPLICITA.get(ch, ch) for ch in texto)
    salida: list = []
    base_latina = False
    for ch in unicodedata.normalize("NFD", texto):
        if unicodedata.combining(ch):
            if not base_latina:
                salida.append(ch)
            continue
        base_latina = unicodedata.name(ch, "").startswith("LATIN")
        salida.append(ch)
    return unicodedata.normalize("NFC", "".join(salida))


def slugify(text: str) -> str:
    """Clave de ruta: minúsculas, guiones, sin puntuación.

    ``\\w`` en modo unicode a propósito: tras plegar los acentos, lo que quede
    fuera de ASCII es un alfabeto sin equivalente (CJK, cirílico) y borrarlo
    dejaría el slug vacío. Se conserva; lo que se quita es puntuación.
    """
    slug = fold_accents(text).lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def slugify_strict(text: str) -> str:
    """Clave de ruta estricta: sin guiones colgando ni dobles."""
    return re.sub(r"-{2,}", "-", slugify(text)).strip("-")


def clave_de_equivalencia(valor: Any) -> Optional[str]:
    """Clave con la que dos valores cuentan como el mismo dato.

    - ``str(valor)``: un ``title: 2026`` que YAML leyó como entero es el título
      ``"2026"``, no otro distinto.
    - NFKC: ``"Ｍi"`` (ancho completo) y ``"ﬁ"`` (ligadura) son ``"Mi"`` y ``"fi"``.
    - ``casefold``: mayúsculas y ``"ß"``/``"ss"`` no distinguen.
    - Espacios colapsados y recortados: ``"MI  TITLE "`` es ``"mi title"``.

    **No** pliega acentos ni quita símbolos: eso es la clave de ruta, y usarla
    aquí haría iguales a ``"Café"`` y ``"Cafe"``, o a ``"C++"`` y ``"C#"``.
    ``None`` y la cadena vacía no tienen clave (``None``).
    """
    if valor is None:
        return None
    texto = unicodedata.normalize("NFKC", str(valor)).casefold()
    texto = " ".join(texto.split())
    return texto or None


def equivalentes(a: Any, b: Any) -> bool:
    """``True`` si ``a`` y ``b`` son el mismo dato según la clave de equivalencia."""
    return clave_de_equivalencia(a) == clave_de_equivalencia(b)


def clave_de_nombre(nombre: Any) -> str:
    """Clave de identidad de una nota por su nombre: a qué fichero apunta un enlace.

    Es la que comparan los wikilinks y los `aliases:` contra el nombre de
    fichero: pliega acentos —``slugify`` translitera al nombrar, así que
    ``Índice.md`` e ``indice.md`` son la misma nota— y quita mayúsculas y los
    separadores ``-``, ``_``, espacio y punto, porque ``[[Mi Proyecto]]``
    apunta a ``mi-proyecto.md``.

    La extensión ``.md`` se quita **antes** que los puntos. Al revés —como hacían
    las cinco copias de v40.35— cualquier nombre terminado en ``md`` perdía esas
    letras: ``cmd.md`` y ``c.md`` daban la misma clave, dos notas con un solo
    ID (AP-17).
    """
    texto = fold_accents(str(nombre)).lower().strip().removesuffix(".md")
    for separador in ("-", "_", " ", "."):
        texto = texto.replace(separador, "")
    return texto
