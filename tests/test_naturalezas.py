"""Las tools de construcción no se confunden con las de documentación.

`CAPACIDADES` responde «¿a qué sirve este grupo?» y se declara **por grupo**.
Esa granularidad no alcanza para la pregunta distinta de «¿sobre qué actúa esta
tool?», porque la mezcla ocurre *dentro* de los grupos: el grupo 1 tiene
`vault_write` junto a `vault_read`, `vault_search` y `vault_move`, y `vault_move`
decide dónde vive una nota mientras los otros tres no tocan la estructura.
`NATURALEZAS` es el segundo eje, declarado por tool.

Lo que estos tests fijan es que el eje sea una partición —exhaustiva y sin
solapes— y que no se pueda desviar del otro eje en su único punto de contacto
verificable.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_servicio as servicio  # noqa: E402
from vault_mcp_catalog import mapa_de_grupos  # noqa: E402


def test_toda_tool_del_catalogo_tiene_naturaleza():
    """Una tool sin naturaleza es una tool sobre la que nadie decidió nada."""
    por_tool = servicio.naturaleza_por_tool()
    huerfanas = sorted(set(mapa_de_grupos()) - set(por_tool))
    assert huerfanas == [], (
        "estas tools no declaran sobre qué actúan: " + ", ".join(huerfanas)
    )


def test_ninguna_naturaleza_nombra_una_tool_que_no_existe():
    desconocidas = sorted(set(servicio.naturaleza_por_tool()) - set(mapa_de_grupos()))
    assert desconocidas == []


def test_las_naturalezas_no_se_solapan():
    """Si una tool cae en dos naturalezas, el eje no clasifica: opina."""
    vistas = {}
    duplicadas = []
    for nombre, datos in servicio.NATURALEZAS.items():
        for tool in datos["tools"]:
            if tool in vistas:
                duplicadas.append(f"{tool}: {vistas[tool]} y {nombre}")
            vistas[tool] = nombre
    assert duplicadas == []


def test_ninguna_naturaleza_esta_vacia():
    """Una naturaleza sin tools es una categoría inventada, no medida."""
    vacias = [n for n, d in servicio.NATURALEZAS.items() if not d["tools"]]
    assert vacias == []


def test_construccion_y_documentacion_son_conjuntos_disjuntos():
    """El encargo, en su forma más literal: no mezclarlas ni confundirlas."""
    construccion = set(servicio.NATURALEZAS["construccion"]["tools"])
    documentacion = set(servicio.NATURALEZAS["documentacion"]["tools"])
    assert construccion & documentacion == set()
    # Y el discriminador escrito, que es lo que permite clasificar la siguiente
    # tool sin volver a discutirlo: continente frente a contenido.
    assert servicio.NATURALEZAS["construccion"]["distincion"].strip()
    assert servicio.NATURALEZAS["documentacion"]["distincion"].strip()


def test_los_dos_ejes_no_se_contradicen_donde_se_tocan():
    """`meta_estandar` y `gobernanza_del_estandar` son el mismo conjunto.

    Es el único solape verificable entre los dos ejes, y por eso es el único
    sitio donde uno puede desmentir al otro. Que coincidan no lo garantiza nada
    salvo esta comprobación: se declaran en registros distintos.
    """
    por_tool = servicio.naturaleza_por_tool()
    por_capacidad = {
        tool for fila in servicio.trazabilidad()
        if fila["capability"] == "gobernanza_del_estandar"
        for tool in [fila["tool"]]
    }
    por_naturaleza = {t for t, n in por_tool.items() if n == "meta_estandar"}
    assert por_naturaleza == por_capacidad


def test_el_check_publica_el_reparto_y_falla_si_algo_se_rompe():
    envelope = servicio.check()
    assert envelope["ok"] is True
    assert envelope["natures_total"] == len(servicio.NATURALEZAS)
    assert sum(envelope["tools_by_nature"].values()) == envelope["tools_total"]
    for clave in ("tools_without_nature", "unknown_tools_in_natures",
                  "duplicated_natures", "empty_natures", "axis_disagreements"):
        assert envelope[clave] == [], clave


def test_la_trazabilidad_publica_la_naturaleza_de_cada_tool():
    filas = servicio.trazabilidad()
    assert filas, "sin filas no hay trazabilidad que comprobar"
    assert all(fila.get("nature") for fila in filas)
