"""La pirámide L0-L3: clasificación MEDIDA desde un JUnit, no por nombres.

Negativas: no existe el JUnit -> error; un fichero con poca mediana pero un
caso larguísimo mantiene su nivel y se ve en la lista de casos únicos caros.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audits" / "architecture"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _modulo():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "piramide_validacion", BASE / "piramide_validacion.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _junit(tmp_path: Path, casos: list[tuple[str, float]]) -> Path:
    """Fixture JUnit mínimo: (classname, segundos) por caso."""
    lineas = ['<testsuites name="pytest">']
    for clase, tiempo in casos:
        lineas.append(f'<testsuite name="{clase}" classname="{clase}">'
                      f'<testcase classname="{clase}" name="x" time="{tiempo}"/>'
                      "</testsuite>")
    lineas.append("</testsuites>")
    ruta = tmp_path / "junit.xml"
    ruta.write_text("".join(lineas), encoding="utf-8")
    return ruta


def test_clasifica_por_mediana_por_caso(tmp_path):
    mod = _modulo()
    casos = [("test_rapido", "0.1")] * 4 + [("test_rapido", "0.2")]
    datos = mod.clasificar(mod.leer_junit(_junit(tmp_path, casos)))
    assert datos["ficheros"][0]["nivel"] == "L0"


def test_el_viaje_unico_no_subio_el_nivel_de_su_fichero(tmp_path):
    """40 casos de 0,1 s y uno de 150 s: nivel L0/L1, no L3 (y no lo esconde)."""
    mod = _modulo()
    casos = ([("test_mezcla", "0.1")] * 40 + [("test_mezcla", "150")])
    datos = mod.clasificar(mod.leer_junit(_junit(tmp_path, casos)))
    ficha = datos["ficheros"][0]
    assert ficha["nivel"] == "L0"
    assert ficha["max_caso"] == 150.0


def test_el_doc_muestra_las_mediana_y_el_caso_caros(tmp_path):
    mod = _modulo()
    casos = ([("test_fix_all", "0.5")] * 30 + [("test_fix_all", "150")])
    j = _junit(tmp_path, casos)
    datos = mod.clasificar(mod.leer_junit(j))
    doc = mod.construir_doc(datos, 100.0)
    assert "| L0 |" in doc
    # el caso único caro aparece con su fichero (sin prefijo duplicado)
    assert "`test_fix_all`" in doc
    assert "test_test_" not in doc
    # el factor de paralelismo se calcula de la medida que entra
    assert "0." in doc and "×" in doc


def test_sin_junit_el_script_falla(tmp_path):
    mod = _modulo()
    with pytest.raises(SystemExit):
        mod.leer_junit(tmp_path / "no-existe.xml")


def test_la_piramide_versionada_es_coherente_con_sus_cortes():
    """El artefacto publicado no puede declarar niveles que no sean los suyos."""
    import statistics

    ruta = BASE / "piramide-niveles.json"
    assert ruta.is_file(), "la pirámide no está publicada"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    for f in datos["ficheros"]:
        mediana = f["mediana_caso"]
        esperado = mod_nivel(mediana)
        assert f["nivel"] == esperado, f
    # niveles válidos y dentro del vocabulario
    assert all(f["nivel"] in ("L0", "L1", "L2", "L3")
               for f in datos["ficheros"])


def mod_nivel(mediana: float) -> str:
    if mediana < 1.0:
        return "L0"
    if mediana < 5.0:
        return "L1"
    if mediana < 30.0:
        return "L2"
    return "L3"


def test_el_doc_versionado_existe_y_deriva():
    ruta = BASE / "PIRAMIDE-VALIDACION.md"
    assert ruta.is_file()
    texto = ruta.read_text(encoding="utf-8")
    assert "mediana del" in texto
    assert "caros" in texto or "extremo" in texto


def test_las_estadisticas_usan_mediana_no_media(tmp_path):
    """La media se arrastraria por un valor atipico: mediana, no media."""
    mod = _modulo()
    casos = [("test_p", "0.1")] * 100 + [("test_p", "1000.0")]
    datos = mod.clasificar(mod.leer_junit(_junit(tmp_path, casos)))
    assert datos["ficheros"][0]["mediana_caso"] == pytest.approx(0.1)
    assert datos["ficheros"][0]["nivel"] == "L0"
