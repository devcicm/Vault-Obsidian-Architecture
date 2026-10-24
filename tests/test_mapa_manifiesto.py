"""F3 — el mapa del manifiesto cruza contra sus titulares reales.

El manifiesto tiene ~12.000 líneas y **no tiene índice**: un lector no puede
distinguir la ley de la plantilla de una nota (los titulares de plantilla viven
dentro de bloques de código, donde un escáner ingenuo los cuenta como
estructura). `docs/MAPA-MANIFIESTO.md` es la clasificación —juicio humano:
decidir qué es ley y qué es guía no se deriva de nada— y este test es la
máquina que vigila que la clasificación esté completa:

- todo titular real del manifiesto está clasificado en el mapa, y
- toda entrada del mapa existe en el manifiesto.

Cualquiera de las dos mitades que deje de cumplirse pone el test en rojo, y
así el mapa no puede envejecer en la dirección cómoda.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

MANIFIESTO = RAIZ / "vault-obsidian-architecture.md"
MAPA = RAIZ / "docs" / "MAPA-MANIFIESTO.md"


def titulares_reales() -> list[str]:
    """Los `## ` del manifiesto que son estructura y no plantilla.

    Consciente de los bloques de código: las plantillas de nota viven dentro
    de fences ```markdown y sus `##` no son estructura del documento — contar
    los contaba titulares que no existen, y el mapa mentía al clasificarlos.
    """
    en_fence = False
    titulares: list[str] = []
    for linea in MANIFIESTO.read_text(encoding="utf-8").split("\n"):
        if linea.strip().startswith("```"):
            en_fence = not en_fence
            continue
        if not en_fence and linea.startswith("## "):
            titulares.append(linea[3:].strip())
    return titulares


def clasificados() -> dict[str, list[str]]:
    """Titular → clases que el mapa le asigna (un titular puede tener dos)."""
    mapa: dict[str, list[str]] = {}
    clase_actual: str | None = None
    for linea in MAPA.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^### (norma|guía|gobierno|registro) — ", linea)
        if m:
            clase_actual = m.group(1)
            continue
        if linea.startswith("| ") and clase_actual and "Titular" not in linea:
            celdas = [c.strip() for c in linea.strip("|").split("|")]
            if not celdas or celdas[0].startswith("--"):
                continue
            titular = celdas[0].strip("`")
            mapa.setdefault(titular, []).append(clase_actual)
    return mapa


def test_cada_titular_real_del_manifiesto_esta_clasificado():
    reales = titulares_reales()
    assert len(reales) >= 20, f"el manifiesto perdió titulares: {len(reales)}"
    mapa = clasificados()
    sin_clasificar = [t for t in reales if t not in mapa]
    assert not sin_clasificar, (
        f"titulares del manifiesto sin clasificar en docs/MAPA-MANIFIESTO.md: "
        f"{sin_clasificar} — se salda clasificándolos, no borrándolos"
    )


def test_cada_entrada_del_mapa_existe_en_el_manifiesto():
    """Un mapa que clasifica titulares que ya no existen miente igual que uno
    incompleto: la entrada se actualiza o se borra."""
    reales = set(titulares_reales())
    mapa = clasificados()
    fantasma = [t for t in mapa if t not in reales]
    assert not fantasma, f"entradas del mapa sin titular en el manifiesto: {fantasma}"


def test_las_clases_del_mapa_son_las_cuatro_declaradas():
    """Si mañana hay una quinta clase, se declara en la tabla del mapa antes
    de usarse: una clase sin definición es una clase que nadie sabe leer."""
    declaradas = {"norma", "guía", "gobierno", "registro"}
    for titular, clases in clasificados().items():
        for c in clases:
            assert c in declaradas, f"{titular}: clase desconocida {c!r}"
    # y las cuatro tienen tabla propia en el mapa
    doc = MAPA.read_text(encoding="utf-8")
    for c in sorted(declaradas):
        assert f"### {c} — " in doc, c


def test_los_titulares_de_plantilla_no_son_estructura():
    """El caso que dio nombre a este test: '## production' y '## {nombre-paquete}'
    viven dentro de fences de plantillas de nota. Si el escáner vuelve a
    contarlos, el mapa tendría que clasificar la documentación de una
    dependencia como si fuera ley."""
    texto = MANIFIESTO.read_text(encoding="utf-8")
    reales = set(titulares_reales())
    assert "production" not in reales, (
        "'## production' es un ejemplo dentro de un bloque; no es estructura"
    )
    assert not any(t.startswith("{nombre-paquete") for t in reales)
