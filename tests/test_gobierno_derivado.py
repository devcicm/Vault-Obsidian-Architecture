import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _r in (RAIZ / "scripts", RAIZ):
    if str(_r) not in sys.path:
        sys.path.insert(0, str(_r))

sys.stdout.reconfigure(encoding="utf-8")

import vault_servicio as vs  # noqa: E402
from vault_gate import PUERTAS  # noqa: E402
from vault_norms_catalog import NORM_CATALOG  # noqa: E402


def test_gobierno_es_derivado_y_estable():
    """Regenerar dos veces produce lo mismo: el doc no tiene estado propio.

    Y el fichero del disco tiene que coincidir con la regeneración — si no,
    alguien lo editó a mano y `check()` debería estar en rojo.
    """
    with_temp = RAIZ / "docs" / "GOBIERNO.md"
    r1 = vs.escribir_doc(ruta=RAIZ / "docs" / "GOBIERNO.md")
    assert r1["ok"], r1
    antes = with_temp.read_text(encoding="utf-8")
    vs.escribir_doc(ruta=RAIZ / "docs" / "GOBIERNO.md")
    assert with_temp.read_text(encoding="utf-8") == antes


def test_gobierno_declara_las_cifras_del_registro():
    """Las cifras del mapa salen de los registros, no de la mano."""
    doc = (RAIZ / "docs" / "GOBIERNO.md").read_text(encoding="utf-8")
    assert f"{len(NORM_CATALOG)} normas vivas" in doc
    por_tipo = {}
    for n in NORM_CATALOG:
        por_tipo[n["type"]] = por_tipo.get(n["type"], 0) + 1
    for tipo, n in por_tipo.items():
        assert f"({n} vigentes)" in doc, f"{tipo}: {n}"


def test_gobierno_distingue_ley_de_mantenimiento():
    """La pregunta del estándar —'esto obliga al consumidor o al mantenedor'—
    tiene que estar respondida en el mapa, no repartida entre cuatro docs."""
    doc = (RAIZ / "docs" / "GOBIERNO.md").read_text(encoding="utf-8")
    assert "Qué es ley para quién" in doc
    assert "gobernanza del meta-toolkit" in doc
    # La cifra la publica `PUERTAS`, y el test la pregunta: repetirla a mano
    # aquí era una segunda fuente para un número que cambia con cada puerta
    # nueva —y la primera vez que se añadía una, el test fue el que cayó.
    assert f"{len(PUERTAS)} puertas" in doc


def test_check_ve_la_deriva_si_el_doc_se_edita_a_mano():
    """AP-47: el doc derivado que se aparta de los registros tiene que poner
    la puerta en rojo — un mapa desfasado miente mejor que ningún mapa."""
    doc = RAIZ / "docs" / "GOBIERNO.md"
    original = doc.read_text(encoding="utf-8")
    try:
        doc.write_text(original + "\n<!-- editado a mano -->\n", encoding="utf-8")
        env = vs.check()
        assert not env["ok"], "una edición a mano en un derivado tiene que fallar"
        assert "difiere" in env["doc_drift"], env["doc_drift"]
    finally:
        doc.write_text(original, encoding="utf-8")
    assert vs.check()["ok"], "restaurado, vuelve a verde"
