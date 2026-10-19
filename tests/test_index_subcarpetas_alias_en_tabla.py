r"""Indice de seccion: el wikilink con `|` rompe la celda de tabla.

Medido 2026-10-18 contra el 01_Projects/index.md de SMART POS CR
(visible en Obsidian como tabla "Subcarpetas" con 4 columnas en vez
de 3, y la columna "Propósito" con el texto huérfano `índice]]`):

    | `01_Projects/smart-pos-cr/` | [[01_Projects/smart-pos-cr/index|índice]] | Estado... |

La `|` del alias actuaba como separador de columna. El detector
`RE_ALIAS_EN_TABLA` (regex en vault/indices/seccion.py) no lo cazaba
porque anclaba al inicio de linea con `^|\\s*` — la fila EMPIEZA con
`| Carpeta`, el wikilink está en la segunda columna, y el regex
exigia wikilink inmediatamente tras el primer `|`. El heal
(`heal_indexes`) regeneraba el index, pero el generador
(linea 262) producia el MISMO bug, asi que el heal creía haberlo
arreglado y no arreglaba nada.

La cura: regex que matchea el patron en cualquier celda de tabla
(linea que empieza con `|`), y el generador emite el wikilink SIN
alias en celdas de tabla (el destino se muestra como el stem).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vault.indices.seccion import (  # noqa: E402
    RE_ALIAS_EN_TABLA,
    RenderizadorDeIndice,
)


def _renderer_con_subcarpeta() -> RenderizadorDeIndice:
    """Un renderizador con describir/pista/enlace triviales, más un
    `indice_disponible` que dice que el `index.md` de la subcarpeta sí
    existe (la rama que el bug ataca)."""
    return RenderizadorDeIndice(
        describir_seccion=lambda clave: f"descripcion de {clave}",
        pista_de_tool=lambda clave: None,
        enlace_seguro=lambda ruta: f"[[{ruta}]]",
        indice_disponible=lambda ruta: ruta.endswith("/index.md"),
    )


def test_generador_no_emite_wikilink_con_alias_en_celda_de_tabla():
    """El bug central: el wikilink de la celda Índice de la tabla de
    Subcarpetas NO debe llevar alias. Un alias ahí contiene `|`, que el
    parser de tablas de Markdown trata como separador de columna y
    parte la fila."""
    r = _renderer_con_subcarpeta()
    md = r.render(
        carpeta="01_Projects",
        notas=[],
        ahora="2026-10-18T00:00:00.000Z",
        subcarpetas=["01_Projects/smart-pos-cr"],
    )
    # La fila de la tabla de Subcarpetas: empieza con `|` y contiene
    # la subcarpeta. Antes del fix el wikilink tenía `|índice` y rompía
    # la celda. Ahora debe ser un wikilink SIN alias.
    filas_tabla = [
        ln for ln in md.splitlines()
        if ln.startswith("|") and "01_Projects/smart-pos-cr/" in ln
    ]
    assert len(filas_tabla) == 1, filas_tabla
    fila = filas_tabla[0]
    # Ninguna celda de la fila puede tener un wikilink con `|` (alias).
    celdas = [c.strip() for c in fila.strip("|").split("|")]
    for celda in celdas:
        assert not re.search(r"\[\[[^\]|]+\|[^\]]+\]\]", celda), (
            f"celda con wikilink-con-alias (rompe la tabla): {celda!r} "
            f"en fila {fila!r}"
        )
    # Y, explícitamente, la celda "Índice" debe contener un wikilink
    # válido (sin pipe), no un path en backticks: el enlace al
    # index.md de la subcarpeta debe ser navegable.
    celda_indice = next((c for c in celdas if "[[" in c), None)
    assert celda_indice is not None
    assert "|" not in celda_indice, (
        f"celda Índice tiene pipe: {celda_indice!r}"
    )
    assert celda_indice.startswith("[[") and celda_indice.endswith("]]")


def test_regex_RE_ALIAS_EN_TABLA_caza_la_fila_real_rota():
    """El detector debe encontrar la fila rota tal y como aparece en
    el vault de SMART POS CR (línea 11 del 01_Projects/index.md)."""
    md = (
        "## Subcarpetas\n"
        "\n"
        "| Carpeta | Índice | Propósito |\n"
        "|---|---|---|\n"
        "| `01_Projects/smart-pos-cr/` | [[01_Projects/smart-pos-cr/index|índice]] | Estado |\n"
    )
    matches = list(RE_ALIAS_EN_TABLA.finditer(md))
    assert len(matches) == 1, f"esperaba 1 match, obtuve {len(matches)}: {[m.group() for m in matches]}"
    assert "índice" in matches[0].group()


def test_regex_RE_ALIAS_EN_TABLA_no_caza_listas_de_navegacion():
    """Los wikilinks-con-alias en la cabecera (migaja, comilla) son
    legítimos: NO están en una celda de tabla. El regex `^|` evita
    falsos positivos ahí."""
    md = (
        "> **↑** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]  ·  [[99_Index/index|índice maestro]]\n"
        "\n"
        "- [[algo|enlace de lista]]\n"
    )
    matches = list(RE_ALIAS_EN_TABLA.finditer(md))
    assert matches == [], (
        f"el detector cazo wikilinks-en-lista (falso positivo): "
        f"{[m.group() for m in matches]}"
    )


def test_generador_con_multiples_subcarpetas_no_mezcla_aliases():
    """Con varias subcarpetas, ninguna fila de la tabla puede tener
    wikilink con alias."""
    r = _renderer_con_subcarpeta()
    md = r.render(
        carpeta="02_Observability",
        notas=[],
        ahora="2026-10-18T00:00:00.000Z",
        subcarpetas=[
            "02_Observability/errors",
            "02_Observability/metricas-y-slis",
            "02_Observability/patrones-de-error",
        ],
    )
    filas_tabla = [
        ln for ln in md.splitlines()
        if ln.startswith("|") and "[[" in ln
    ]
    assert len(filas_tabla) == 3
    for fila in filas_tabla:
        celdas = [c.strip() for c in fila.strip("|").split("|")]
        for celda in celdas:
            assert not re.search(r"\[\[[^\]|]+\|[^\]]+\]\]", celda), (
                f"celda con alias en fila {fila!r}: {celda!r}"
            )


def test_generador_sin_indice_disponible_no_enlaza():
    """Si el `index.md` de la subcarpeta NO existe (o no se escribe en
    esta corrida), el generador pone el path en backticks en vez de
    un wikilink — no se inventa el link."""
    r = RenderizadorDeIndice(
        describir_seccion=lambda clave: "x",
        pista_de_tool=lambda clave: None,
        enlace_seguro=lambda ruta: f"[[{ruta}]]",
        indice_disponible=lambda ruta: False,
    )
    md = r.render(
        carpeta="01_Projects",
        notas=[],
        ahora="2026-10-18T00:00:00.000Z",
        subcarpetas=["01_Projects/smart-pos-cr"],
    )
    fila = [ln for ln in md.splitlines() if ln.startswith("|") and "01_Projects/smart-pos-cr" in ln]
    assert len(fila) == 1
    assert "[[" not in fila[0]  # sin wikilink, path en backticks
    assert "`01_Projects/smart-pos-cr/index.md`" in fila[0]
