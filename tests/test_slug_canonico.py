"""El slug es uno solo, y translitera.

Síntoma real: `vault_onboard` contra un proyecto en español (FastApi NetCore,
ajeno al estándar) escribió `caracter-sticas-principales.md`, `ndice.md`,
`prop-sito-y-beneficios.md`. Su `_slug` casaba `[^a-z0-9]+`, que no translitera
los acentos: los borra, y el wikilink hereda el destrozo.

Al buscar el fallo aparecieron 22 implementaciones de slug repartidas por
`scripts/`, en dos familias divergentes —una conservaba los acentos en el nombre
de fichero, la otra los borraba—. El defecto no era el regex de un módulo: era
que no había fuente única. Es el mismo fallo que `vault_folder_registry` con sus
13 secciones de 22, y se cierra igual: derivación + guard anti-drift.

`vault-sandbox/` no podía revelarlo. Lo genera este repo, en inglés, y sin un
solo carácter fuera de ASCII no hay nada que transliterar (regla 7 de CLAUDE.md,
corolario de AP-44: toda medida nueva se contrasta contra material ajeno).
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_io import normalize_stem  # noqa: E402
from vault_lib import fold_accents, slugify, slugify_strict  # noqa: E402


# ── Comportamiento ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "titulo,esperado",
    [
        ("Índice", "indice"),
        ("Características principales", "caracteristicas-principales"),
        ("Propósito y beneficios", "proposito-y-beneficios"),
        ("Configuración y despliegue", "configuracion-y-despliegue"),
        ("Diseño del módulo", "diseno-del-modulo"),
        ("Añadir política de caché", "anadir-politica-de-cache"),
        ("Über-Straße", "uber-strasse"),
        ("Café  &  Crème", "cafe-creme"),
    ],
)
def test_los_acentos_se_transliteran_no_se_borran(titulo, esperado):
    assert slugify_strict(titulo) == esperado


def test_ningun_slug_conserva_caracteres_no_ascii_latinos():
    """El nombre de fichero es una interfaz: tiene que ser tecleable."""
    for titulo in ("Índice", "Añadido", "Configuración"):
        assert slugify(titulo).isascii(), titulo


def test_un_alfabeto_sin_equivalente_ascii_no_se_borra():
    """Plegar acentos no es lo mismo que exigir ASCII.

    Si el regex fuese `[^a-z0-9]+`, un título en cirílico o CJK daría slug
    vacío y la nota acabaría en un fichero sin nombre. Se conserva.
    """
    assert slugify("Заметка") == "заметка"
    assert slugify_strict("日本語 ノート") == "日本語-ノート"


def test_el_slug_no_deja_guiones_colgando_ni_dobles():
    assert slugify_strict("-- Hola --- Mundo --") == "hola-mundo"


def test_fold_accents_es_idempotente():
    for t in ("Índice", "indice", "Straße"):
        assert fold_accents(fold_accents(t)) == fold_accents(t)


def test_la_nota_acentuada_previa_y_la_nueva_son_la_misma_nota():
    """Sin esto, transliterar habría duplicado cada nota acentuada existente.

    `Índice.md` se escribió antes del cambio; `indice.md` es lo que se derivaría
    hoy. Si el criterio de comparación no pliega acentos, el vault termina con
    las dos y ninguna tool lo nota.
    """
    assert normalize_stem("Índice") == normalize_stem("indice.md")
    assert normalize_stem("Diseño Módulo") == normalize_stem("diseno-modulo.md")


# ── Guard anti-drift: una sola fuente ─────────────────────────────────────────

#: `vault_write.slugify` no delega a propósito: usa
#: `vault_encoding.sanitize_filename`, que resuelve además caracteres inválidos
#: por plataforma, invisibles y longitud máxima. Es un contrato distinto —el del
#: write path canónico—, no una copia del slug. Se anota, no se borra.
_DELEGACION_JUSTIFICADA = {"vault_write.py": "usa vault_encoding.sanitize_filename"}


def _definiciones_de_slug():
    for py in sorted(list((REPO_ROOT / "scripts").glob("*.py")) + list((REPO_ROOT / "cli").glob("*.py"))):
        if py.name == "vault_lib.py":
            continue  # la fuente
        arbol = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.FunctionDef) and nodo.name in ("slugify", "_slug"):
                yield py, nodo


def test_ningun_modulo_implementa_su_propio_slug():
    """La copia 23 no entra.

    Un módulo puede llamarse `slugify`, pero su cuerpo tiene que delegar en
    `vault_lib`. Se detecta por el regex: si vuelve a aparecer un `re.sub` sobre
    el texto de entrada, es una implementación propia.
    """
    culpables = []
    for py, nodo in _definiciones_de_slug():
        if py.name in _DELEGACION_JUSTIFICADA:
            continue
        cuerpo = ast.dump(nodo)
        delega = "slugify_strict" in cuerpo or "slugify" in cuerpo.replace(f"'{nodo.name}'", "")
        if not delega or "re.sub" in ast.unparse(nodo):
            culpables.append(f"{py.name}:{nodo.lineno}")
    assert not culpables, (
        "módulos con slug propio en vez de delegar en vault_lib.slugify: "
        f"{culpables}"
    )


def test_la_justificacion_no_se_queda_obsoleta():
    """Si `vault_write` deja de tener slug propio, la excepción sobra."""
    con_slug = {py.name for py, _ in _definiciones_de_slug()}
    huerfanas = set(_DELEGACION_JUSTIFICADA) - con_slug
    assert not huerfanas, f"excepciones sin módulo detrás: {sorted(huerfanas)}"
