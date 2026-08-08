"""El filtro de las expresiones regulares del estándar.

Las regex de este repo no son detalle de implementación: son el **filtro por el
que pasa el dato ajeno**. `vault_ingest` es la única superficie de escritura, y
lo que entra por ahí lo leen después los extractores de wikilinks, el auditor de
normas y el validador de mermaid. Una regex mala en ese camino no da un
resultado peor: da un resultado *distinto* del que el consumidor espera, o no da
ninguno porque la tool se quedó colgada.

Este fichero barre **todas** las regex literales de `scripts/`, `cli/` y
`vault/` por AST —no por grep, que cuenta las de dentro de docstrings— y les
exige cuatro cosas:

1. **Compilan sin avisos.** `vault_regex.RE_MIXED_BRACKETS` se escribía con los
   ejemplos literales en los comentarios de un patrón `re.VERBOSE`, y el
   compilador leía los corchetes del comentario: `FutureWarning: Possible nested
   set`. El día que Python lo convierta en error, el módulo que valida cada
   wikilink de cada vault deja de importarse.
2. **Ninguna casa la cadena vacía.** Un patrón que acepta el vacío convierte
   «no encontré nada» en «encontré algo vacío», que es la forma de AP-51 que
   vive en las regex: el fallo se presenta como un dato.
3. **Ninguna escala peor que lineal.** Es la propiedad cara. Una línea de
   64.000 espacios tardaba 137 segundos en el detector de marcadores
   pendientes, y una tirada de corchetes ponía el extractor de wikilinks en
   cuadrático limpio. Ambas entradas llegan por `vault_ingest` desde material
   que el estándar no escribió.
4. **Los patrones de ruta entienden los dos separadores.** Un patrón que solo
   contempla `/` mide de menos en Windows, que es donde este repo se desarrolla.

El barrido es un guard, no una lista: una regex nueva entra en él sin que nadie
la registre. Es a propósito — el registro que hay que acordarse de actualizar es
el que se queda atrás.
"""

import ast
import re
import sys
import time
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

#: Métodos de `re` cuyo primer argumento posicional es el patrón.
_METODOS_RE = {
    "compile", "match", "search", "fullmatch",
    "findall", "finditer", "sub", "subn", "split",
}

#: Umbral de la comprobación de escala. Los cebos son de 2.000 caracteres; un
#: patrón lineal los resuelve en microsegundos, así que 50 ms ya es un factor
#: enorme. No se afina más: medir tiempos en CI es ruidoso y lo que se busca
#: aquí es la diferencia entre lineal y cuadrático, no una regresión de un 20%.
_UMBRAL_MS = 50.0

#: Entradas hostiles: tiradas del mismo carácter, que es lo que dispara el
#: retroceso cuando un cuantificador goloso puede empezar en cada posición.
_CEBOS = [
    " " * 2000,
    "\t" * 2000,
    "a" * 2000,
    "[" * 2000,
    "]" * 2000,
    "[[" * 1000,
    "-" * 2000,
    "#" * 2000,
    "*" * 2000,
    "x " * 1000,
]


def _regex_literales():
    """Toda regex escrita como literal en el código, con su ubicación.

    Por AST y no por grep: los ejemplos de dentro de las docstrings —incluido
    el de `vault_error_contract`, que documenta lo que **no** hay que hacer— no
    son código y no deben contarse.
    """
    encontradas = []
    for carpeta in ("scripts", "cli", "vault"):
        raiz = REPO_ROOT / carpeta
        if not raiz.exists():
            continue
        for fichero in sorted(raiz.rglob("*.py")):
            # `_archived/` guarda lo reemplazado por la no-derogación: se
            # conserva por contrato, no se ejecuta. Exigirle propiedades a
            # código que nadie llama convierte el guard en ruido.
            if "_archived" in fichero.parts:
                continue
            try:
                arbol = ast.parse(fichero.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for nodo in ast.walk(arbol):
                if not (isinstance(nodo, ast.Call)
                        and isinstance(nodo.func, ast.Attribute)
                        and nodo.func.attr in _METODOS_RE
                        and getattr(nodo.func.value, "id", "") == "re"
                        and nodo.args):
                    continue
                primero = nodo.args[0]
                if isinstance(primero, ast.Constant) and isinstance(
                        primero.value, str):
                    ruta = fichero.relative_to(REPO_ROOT).as_posix()
                    encontradas.append((f"{ruta}:{nodo.lineno}", primero.value))
    return encontradas


REGEX = _regex_literales()


def test_el_barrido_encuentra_regex():
    """Si el extractor se rompe, los otros tres tests pasan vacíos.

    Un guard que no encuentra nada no se distingue de uno que ya no tiene nada
    que encontrar. El umbral es holgado a propósito: mide que el AST sigue
    funcionando, no cuántas regex hay —eso sería una cifra a mano, AP-47—.
    """
    assert len(REGEX) > 200, (
        f"el extractor por AST solo encontró {len(REGEX)} regex; el barrido "
        "está midiendo de menos y los demás tests de este fichero no prueban "
        "nada")


def test_ninguna_regex_compila_con_aviso():
    """Compilar con `FutureWarning` es un error diferido, no un aviso.

    El caso real: los comentarios de un patrón `re.VERBOSE` llevaban los
    ejemplos literales (`# ][[`) y el compilador leía esos corchetes.
    """
    culpables = []
    for ubicacion, patron in REGEX:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            try:
                re.compile(patron)
            except Exception as exc:  # noqa: BLE001 — el tipo va en el informe
                culpables.append(f"{ubicacion}: {type(exc).__name__}: {exc}")
    assert not culpables, "regex que no compilan limpias:\n  " + "\n  ".join(
        culpables)


def test_ninguna_regex_casa_la_cadena_vacia():
    """Un patrón que acepta el vacío devuelve hallazgos que no existen."""
    culpables = [
        f"{ubicacion}: {patron[:60]!r}"
        for ubicacion, patron in REGEX
        if re.compile(patron).match("")
    ]
    assert not culpables, (
        "regex que casan la cadena vacía y por tanto encuentran algo en la "
        "nada:\n  " + "\n  ".join(culpables))


def test_ninguna_regex_escala_peor_que_lineal():
    """La propiedad cara: entrada hostil de 2.000 caracteres, en milisegundos.

    Las dos que fallaban llegaban desde material ajeno vía `vault_ingest`: una
    línea de espacios en el detector de marcadores pendientes y una tirada de
    corchetes en el extractor de wikilinks.
    """
    lentas = []
    for ubicacion, patron in REGEX:
        try:
            compilada = re.compile(patron)
        except Exception:  # noqa: BLE001 — lo reporta el test de compilación
            continue
        peor = 0.0
        for cebo in _CEBOS:
            inicio = time.perf_counter()
            try:
                compilada.search(cebo)
            except Exception:  # noqa: BLE001 — idem
                pass
            peor = max(peor, (time.perf_counter() - inicio) * 1000)
        if peor > _UMBRAL_MS:
            lentas.append(f"{ubicacion}: {peor:.0f} ms — {patron[:50]!r}")
    assert not lentas, (
        f"regex que tardan más de {_UMBRAL_MS:.0f} ms con 2.000 caracteres "
        "hostiles; a escala de una nota real eso es un cuelgue:\n  "
        + "\n  ".join(lentas))


def test_el_extractor_de_wikilinks_tiene_un_solo_dueno():
    """AP-50: la decisión se toma en `vault_regex`, no en nueve módulos.

    Estaba escrito a mano en nueve sitios y las copias divergían: ocho
    extraían `Nota#Sección` como destino —un fichero que no existe— y solo
    `vault_foreign_check`, la tool de la regla 7, resolvía el ancla. Encima
    todas eran cuadráticas. El guard no mira la lentitud (de eso va el test
    anterior) sino la reaparición de la copia.

    Se marca la **forma concreta** que se consolidó —destino capturado más
    rama de alias opcional— y no cualquier patrón que mencione corchetes: el
    detector de enlaces vacíos, la fila de tabla del índice de secciones y el
    anclado a ruta de `cli/safety.py` son decisiones distintas con dueño
    propio, y acusarlas convertiría el guard en ruido que alguien desactiva.
    """
    # Destino capturado con clase negada, seguido de una alternativa opcional:
    # `\[\[([^\]...]+)(?:...)?\]\]`. Es la firma del extractor, no la de
    # cualquier uso de `[[`.
    firma = re.compile(r"\\\[\\\[\(\[\^[^)]*\]\+\)\(\?:")
    culpables = [
        f"{ubicacion}: {patron[:50]!r}"
        for ubicacion, patron in REGEX
        if firma.search(patron)
        and not ubicacion.startswith("scripts/vault_regex.py")
    ]
    assert not culpables, (
        "extractores de wikilink escritos a mano fuera de vault_regex; usa "
        "RE_WIKILINK, RE_WIKILINK_CON_ALIAS o RE_WIKILINK_DESTINO:\n  "
        + "\n  ".join(culpables))


def test_las_tres_variantes_del_dueno_coinciden_donde_deben():
    """Las tres se conservan porque difieren a propósito, no por descuido.

    `RE_WIKILINK_DESTINO` resuelve el ancla de encabezado; las otras dos no.
    Fijar aquí en qué coinciden y en qué no evita que alguien las "unifique"
    creyendo que la diferencia era un despiste.
    """
    from vault_regex import (RE_WIKILINK, RE_WIKILINK_CON_ALIAS,
                             RE_WIKILINK_DESTINO)

    assert RE_WIKILINK.findall("[[Nota|alias]]") == ["Nota"]
    assert RE_WIKILINK_CON_ALIAS.findall("[[Nota|alias]]") == [("Nota", "alias")]
    assert RE_WIKILINK_DESTINO.findall("[[Nota|alias]]") == ["Nota"]

    # La diferencia declarada: el ancla de encabezado.
    assert RE_WIKILINK.findall("[[Nota#Seccion]]") == ["Nota#Seccion"]
    assert RE_WIKILINK_DESTINO.findall("[[Nota#Seccion]]") == ["Nota"]

    # Ninguna inventa un enlace atravesando corchetes rotos. La versión vieja
    # sí lo hacía: sobre el manifiesto extraía "enlaces" de un párrafo entero.
    roto = "texto [[[[nota]] mas texto y luego [[Buena]]"
    for patron in (RE_WIKILINK, RE_WIKILINK_DESTINO):
        assert "Buena" in patron.findall(roto)
        assert not any(" mas texto" in x for x in patron.findall(roto))


def test_ningun_patron_de_ruta_ignora_el_separador_de_windows():
    """Una ruta se escribe con `\\` en la plataforma donde se desarrolla esto.

    Solo se miran los patrones que hablan de rutas —los que citan una carpeta
    del vault o una extensión— para no acusar a cualquier `/` suelto.
    """
    pista = re.compile(r"\d\d_[A-Z]|\\\.md|/\*\*|00_System")
    culpables = [
        f"{ubicacion}: {patron[:60]!r}"
        for ubicacion, patron in REGEX
        if pista.search(patron) and "/" in patron and "\\\\" not in patron
    ]
    assert not culpables, (
        "patrones de ruta que solo contemplan `/` y por tanto miden de menos "
        "en Windows:\n  " + "\n  ".join(culpables))
